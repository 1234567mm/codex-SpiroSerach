package localbackend

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"spirosearch/internal/sourceregistry"

	_ "modernc.org/sqlite"
)

const SchemaVersionValue = "v33c.local_backend.v1"

var readModelTables = []string{
	"provider_snapshots",
	"provider_sync_jobs",
	"provider_sync_cursors",
	"htl_device_records",
	"review_items",
}

type Reader struct {
	db *sql.DB
}

type ProviderSnapshot struct {
	SnapshotID    string
	Provider      string
	QueryHash     string
	SourceURL     sql.NullString
	RetrievedAt   string
	RawPath       string
	RawSHA256     string
	SchemaVersion string
}

type SyncJob struct {
	JobID      string
	Provider   string
	Status     string
	StartedAt  sql.NullString
	FinishedAt sql.NullString
	Config     map[string]any
	CreatedAt  string
}

type SyncCursor struct {
	JobID          string
	PageIndex      int
	PageAfterValue sql.NullString
	IsLast         bool
	RetrievedAt    string
}

type HtlDevice struct {
	RecordID         string
	EntryID          sql.NullString
	HTLName          string
	ArchiveStatus    string
	SourceSnapshotID sql.NullString
	RetrievedAt      string
}

type ReviewItem struct {
	ReviewID         string
	SourceType       string
	SourceID         string
	Reason           string
	ResolutionStatus string
	CreatedAt        string
}

type SourceRuntimeSummary struct {
	Provider         string
	LiveEnabled      bool
	LocalDataset     bool
	SnapshotCount    int
	LatestSnapshotAt string
	SyncJobCount     int
	LatestSyncStatus string
	DeviceCount      int
	OpenReviewCount  int
}

type ValidationSummary struct {
	SchemaVersion string
	TableCounts   map[string]int
}

func OpenReadOnly(path string) (*Reader, error) {
	if _, err := os.Stat(path); err != nil {
		return nil, err
	}
	uri, err := sqliteReadOnlyURI(path)
	if err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite", uri)
	if err != nil {
		return nil, err
	}
	if err := db.Ping(); err != nil {
		db.Close()
		return nil, err
	}
	return &Reader{db: db}, nil
}

func (r *Reader) Close() error {
	return r.db.Close()
}

func (r *Reader) SchemaVersion(ctx context.Context) (string, error) {
	var value string
	err := r.db.QueryRowContext(ctx, "SELECT value FROM schema_meta WHERE key = 'schema_version'").Scan(&value)
	return value, err
}

func (r *Reader) ValidateReadModel(ctx context.Context) (ValidationSummary, error) {
	version, err := r.SchemaVersion(ctx)
	if err != nil {
		return ValidationSummary{}, err
	}
	if version != SchemaVersionValue {
		return ValidationSummary{}, fmt.Errorf("unknown schema_version: %s", version)
	}
	counts := make(map[string]int, len(readModelTables))
	for _, table := range readModelTables {
		count, err := r.countRows(ctx, table, "")
		if err != nil {
			return ValidationSummary{}, fmt.Errorf("%s: %w", table, err)
		}
		counts[table] = count
	}
	return ValidationSummary{
		SchemaVersion: version,
		TableCounts:   counts,
	}, nil
}

func (r *Reader) ListSnapshots(ctx context.Context, provider string) ([]ProviderSnapshot, error) {
	query := "SELECT snapshot_id, provider, query_hash, source_url, retrieved_at, raw_path, raw_sha256, schema_version FROM provider_snapshots"
	args := []any{}
	if strings.TrimSpace(provider) != "" {
		query += " WHERE provider = ?"
		args = append(args, provider)
	}
	query += " ORDER BY retrieved_at"
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var snapshots []ProviderSnapshot
	for rows.Next() {
		var snapshot ProviderSnapshot
		if err := rows.Scan(
			&snapshot.SnapshotID,
			&snapshot.Provider,
			&snapshot.QueryHash,
			&snapshot.SourceURL,
			&snapshot.RetrievedAt,
			&snapshot.RawPath,
			&snapshot.RawSHA256,
			&snapshot.SchemaVersion,
		); err != nil {
			return nil, err
		}
		snapshots = append(snapshots, snapshot)
	}
	return snapshots, rows.Err()
}

func (r *Reader) ListSyncJobs(ctx context.Context, provider string) ([]SyncJob, error) {
	query := "SELECT job_id, provider, status, started_at, finished_at, config_json, created_at FROM provider_sync_jobs"
	args := []any{}
	if strings.TrimSpace(provider) != "" {
		query += " WHERE provider = ?"
		args = append(args, provider)
	}
	query += " ORDER BY created_at DESC"
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var jobs []SyncJob
	for rows.Next() {
		var job SyncJob
		var configRaw string
		if err := rows.Scan(
			&job.JobID,
			&job.Provider,
			&job.Status,
			&job.StartedAt,
			&job.FinishedAt,
			&configRaw,
			&job.CreatedAt,
		); err != nil {
			return nil, err
		}
		if err := json.Unmarshal([]byte(configRaw), &job.Config); err != nil {
			return nil, fmt.Errorf("sync job %s config_json: %w", job.JobID, err)
		}
		jobs = append(jobs, job)
	}
	return jobs, rows.Err()
}

func (r *Reader) LastCursor(ctx context.Context, jobID string) (*SyncCursor, error) {
	row := r.db.QueryRowContext(
		ctx,
		`SELECT job_id, page_index, page_after_value, is_last, retrieved_at
		 FROM provider_sync_cursors
		 WHERE job_id = ?
		 ORDER BY page_index DESC
		 LIMIT 1`,
		jobID,
	)
	var cursor SyncCursor
	var isLast int
	if err := row.Scan(
		&cursor.JobID,
		&cursor.PageIndex,
		&cursor.PageAfterValue,
		&isLast,
		&cursor.RetrievedAt,
	); err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}
	cursor.IsLast = isLast != 0
	return &cursor, nil
}

func (r *Reader) ListHtlDevices(ctx context.Context, htlName string) ([]HtlDevice, error) {
	query := "SELECT record_id, entry_id, htl_name, archive_status, source_snapshot_id, retrieved_at FROM htl_device_records"
	args := []any{}
	if strings.TrimSpace(htlName) != "" {
		query += " WHERE htl_name = ?"
		args = append(args, htlName)
	}
	query += " ORDER BY retrieved_at"
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var devices []HtlDevice
	for rows.Next() {
		var device HtlDevice
		if err := rows.Scan(
			&device.RecordID,
			&device.EntryID,
			&device.HTLName,
			&device.ArchiveStatus,
			&device.SourceSnapshotID,
			&device.RetrievedAt,
		); err != nil {
			return nil, err
		}
		devices = append(devices, device)
	}
	return devices, rows.Err()
}

func (r *Reader) ListOpenReviewItems(ctx context.Context) ([]ReviewItem, error) {
	rows, err := r.db.QueryContext(
		ctx,
		`SELECT review_id, source_type, source_id, reason, resolution_status, created_at
		 FROM review_items
		 WHERE resolution_status = 'open'
		 ORDER BY created_at`,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var items []ReviewItem
	for rows.Next() {
		var item ReviewItem
		if err := rows.Scan(
			&item.ReviewID,
			&item.SourceType,
			&item.SourceID,
			&item.Reason,
			&item.ResolutionStatus,
			&item.CreatedAt,
		); err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (r *Reader) BuildSourceRuntimeSummary(
	ctx context.Context,
	entries []sourceregistry.Entry,
) ([]SourceRuntimeSummary, error) {
	summaries := make([]SourceRuntimeSummary, 0, len(entries))
	for _, entry := range entries {
		snapshotCount, latestSnapshotAt, err := r.providerSnapshotStats(ctx, entry.Provider)
		if err != nil {
			return nil, err
		}
		syncJobCount, latestSyncStatus, err := r.providerSyncStats(ctx, entry.Provider)
		if err != nil {
			return nil, err
		}
		openReviewCount, err := r.openReviewCountForProvider(ctx, entry.Provider)
		if err != nil {
			return nil, err
		}
		deviceCount := 0
		if entry.Provider == "nomad_perla_psc" {
			deviceCount, err = r.countRows(ctx, "htl_device_records", "")
			if err != nil {
				return nil, err
			}
		}
		summaries = append(summaries, SourceRuntimeSummary{
			Provider:         entry.Provider,
			LiveEnabled:      entry.LiveEnabled(),
			LocalDataset:     entry.LocalDataset(),
			SnapshotCount:    snapshotCount,
			LatestSnapshotAt: latestSnapshotAt,
			SyncJobCount:     syncJobCount,
			LatestSyncStatus: latestSyncStatus,
			DeviceCount:      deviceCount,
			OpenReviewCount:  openReviewCount,
		})
	}
	return summaries, nil
}

func (r *Reader) providerSnapshotStats(ctx context.Context, provider string) (int, string, error) {
	row := r.db.QueryRowContext(
		ctx,
		`SELECT COUNT(*), COALESCE(MAX(retrieved_at), '')
		 FROM provider_snapshots
		 WHERE provider = ? OR provider = ?`,
		provider,
		provider+"_archive",
	)
	var count int
	var latest string
	if err := row.Scan(&count, &latest); err != nil {
		return 0, "", err
	}
	return count, latest, nil
}

func (r *Reader) providerSyncStats(ctx context.Context, provider string) (int, string, error) {
	rows, err := r.db.QueryContext(
		ctx,
		`SELECT status
		 FROM provider_sync_jobs
		 WHERE provider = ?
		 ORDER BY created_at DESC`,
		provider,
	)
	if err != nil {
		return 0, "", err
	}
	defer rows.Close()

	count := 0
	latestStatus := ""
	for rows.Next() {
		var status string
		if err := rows.Scan(&status); err != nil {
			return 0, "", err
		}
		if count == 0 {
			latestStatus = status
		}
		count++
	}
	return count, latestStatus, rows.Err()
}

func (r *Reader) openReviewCountForProvider(ctx context.Context, provider string) (int, error) {
	archiveProvider := provider + "_archive"
	row := r.db.QueryRowContext(
		ctx,
		`SELECT COUNT(*)
		 FROM review_items AS review
		 WHERE review.resolution_status = 'open'
		   AND (
		     (
		       review.source_type = 'provider_snapshot'
		       AND review.source_id IN (
		         SELECT snapshot_id
		         FROM provider_snapshots
		         WHERE provider = ? OR provider = ?
		       )
		     )
		     OR (
		       review.source_type IN ('sync_job', 'provider_sync_job')
		       AND review.source_id IN (
		         SELECT job_id
		         FROM provider_sync_jobs
		         WHERE provider = ?
		       )
		     )
		     OR (
		       review.source_type = 'htl_device'
		       AND review.source_id IN (
		         SELECT device.record_id
		         FROM htl_device_records AS device
		         JOIN provider_snapshots AS snapshot
		           ON device.source_snapshot_id = snapshot.snapshot_id
		         WHERE snapshot.provider = ? OR snapshot.provider = ?
		       )
		     )
		   )`,
		provider,
		archiveProvider,
		provider,
		provider,
		archiveProvider,
	)
	var count int
	if err := row.Scan(&count); err != nil {
		return 0, err
	}
	return count, nil
}

func (r *Reader) countRows(ctx context.Context, table string, where string, args ...any) (int, error) {
	query := "SELECT COUNT(*) FROM " + table
	if where != "" {
		query += " WHERE " + where
	}
	var count int
	if err := r.db.QueryRowContext(ctx, query, args...).Scan(&count); err != nil {
		return 0, err
	}
	return count, nil
}

func sqliteReadOnlyURI(path string) (string, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", err
	}
	slashPath := filepath.ToSlash(absolute)
	if runtime.GOOS == "windows" && len(slashPath) >= 2 && slashPath[1] == ':' {
		slashPath = "/" + slashPath
	}
	uri := url.URL{
		Scheme: "file",
		Path:   slashPath,
	}
	values := uri.Query()
	values.Set("mode", "ro")
	uri.RawQuery = values.Encode()
	return uri.String(), nil
}
