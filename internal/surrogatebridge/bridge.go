/*
	Go bridge for the Python sklearn surrogate (T37-09).

Spawns `python -m spirosearch.surrogate_bridge` and speaks the
line-oriented JSON protocol over stdin/stdout. A fake bridge provides
offline Go tests without a Python runtime or the `[ml]` extras.
*/
package surrogatebridge

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"time"
)

const SchemaVersion = "v37.surrogate_bridge.v1"

// ErrBridgeUnavailable is returned when the Python bridge cannot start.
var ErrBridgeUnavailable = errors.New("surrogate bridge unavailable")

// Provenance is the model lineage attached to every prediction.
type Provenance struct {
	ModelID          string   `json:"model_id"`
	SurrogateType    string   `json:"surrogate_type"`
	TrainingSetHash  string   `json:"training_set_hash"`
	FeatureNames     []string `json:"feature_names"`
	PosteriorVersion int      `json:"posterior_version"`
}

// FitResult mirrors the Python ModelFitResult for the fit action.
type FitResult struct {
	State   map[string]any `json:"state"`
	Metrics map[string]any `json:"metrics"`
}

// Response is the validated bridge response.
type Response struct {
	OK            bool        `json:"ok"`
	SchemaVersion string      `json:"schema_version"`
	Action        string      `json:"action"`
	ModelID       string      `json:"model_id"`
	Values        []float64   `json:"values"`
	Provenance    *Provenance `json:"provenance"`
	FitResult     *FitResult  `json:"fit_result"`
	ErrorCode     string      `json:"error_code"`
	Message       string      `json:"message"`
}

// Bridge executes surrogate actions against a Python child process.
type Bridge interface {
	Fit(ctx context.Context, modelID string, X []map[string]float64, y []float64) (*Response, error)
	Predict(ctx context.Context, modelID string, X []map[string]float64) (*Response, error)
	Uncertainty(ctx context.Context, modelID string, X []map[string]float64) (*Response, error)
	Acquisition(ctx context.Context, modelID string, X []map[string]float64, strategy string) (*Response, error)
	Stop() error
}

// ProcessBridge is the real child-process implementation.
type ProcessBridge struct {
	cmd     *exec.Cmd
	stdin   io.WriteCloser
	scanner *bufio.Scanner
	stderr  *stderrBuffer
	timeout time.Duration
}

// stderrBuffer keeps the child's recent stderr for diagnostics.
type stderrBuffer struct {
	buf []byte
}

func (b *stderrBuffer) Write(p []byte) (int, error) {
	const max = 64 * 1024
	if len(b.buf)+len(p) > max {
		keep := max - len(p)
		if keep < 0 {
			keep = 0
		}
		b.buf = append(b.buf[len(b.buf)-keep:], p...)
	} else {
		b.buf = append(b.buf, p...)
	}
	return len(p), nil
}

func (b *stderrBuffer) String() string {
	return string(b.buf)
}

// Options configures the process bridge.
type Options struct {
	PythonExe string        // default "python"
	Module    string        // default "spirosearch.surrogate_bridge"
	Timeout   time.Duration // per-request timeout, default 60s
	Env       []string      // extra environment for the child, e.g. PYTHONPATH=src
}

// Start launches the Python surrogate bridge child process.
func Start(ctx context.Context, options Options) (*ProcessBridge, error) {
	pythonExe := options.PythonExe
	if pythonExe == "" {
		pythonExe = "python"
	}
	module := options.Module
	if module == "" {
		module = "spirosearch.surrogate_bridge"
	}
	timeout := options.Timeout
	if timeout == 0 {
		timeout = 60 * time.Second
	}
	cmd := exec.CommandContext(ctx, pythonExe, "-m", module)
	cmd.Env = append(os.Environ(), options.Env...)
	stderr := &stderrBuffer{}
	cmd.Stderr = stderr
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("%w: stdin pipe: %v", ErrBridgeUnavailable, err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("%w: stdout pipe: %v", ErrBridgeUnavailable, err)
	}
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("%w: %v (stderr: %s)", ErrBridgeUnavailable, err, stderr.String())
	}
	return &ProcessBridge{
		cmd:     cmd,
		stdin:   stdin,
		scanner: newLargeScanner(stdout),
		stderr:  stderr,
		timeout: timeout,
	}, nil
}

// newLargeScanner supports response lines far beyond the 64KB default.
func newLargeScanner(reader io.Reader) *bufio.Scanner {
	scanner := bufio.NewScanner(reader)
	scanner.Buffer(make([]byte, 1024*1024), 64*1024*1024)
	return scanner
}

func (b *ProcessBridge) request(ctx context.Context, payload map[string]any) (*Response, error) {
	raw, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	if _, err := b.stdin.Write(append(raw, '\n')); err != nil {
		return nil, fmt.Errorf("%w: write: %v", ErrBridgeUnavailable, err)
	}
	lineCh := make(chan string, 1)
	errCh := make(chan error, 1)
	go func() {
		if !b.scanner.Scan() {
			errCh <- b.scanner.Err()
			return
		}
		lineCh <- b.scanner.Text()
	}()
	select {
	case line := <-lineCh:
		var response Response
		if err := json.Unmarshal([]byte(line), &response); err != nil {
			return nil, fmt.Errorf("%w: bad response line: %v", ErrBridgeUnavailable, err)
		}
		if !response.OK {
			return nil, fmt.Errorf("surrogate bridge error %s: %s", response.ErrorCode, response.Message)
		}
		return &response, nil
	case err := <-errCh:
		if err != nil {
			return nil, fmt.Errorf("%w: %v (stderr: %s)", ErrBridgeUnavailable, err, b.stderr.String())
		}
		return nil, fmt.Errorf("%w: child exited (stderr: %s)", ErrBridgeUnavailable, b.stderr.String())
	case <-time.After(b.timeout):
		return nil, fmt.Errorf("%w: request timeout", ErrBridgeUnavailable)
	case <-ctx.Done():
		return nil, ctx.Err()
	}
}

func (b *ProcessBridge) Fit(ctx context.Context, modelID string, X []map[string]float64, y []float64) (*Response, error) {
	return b.request(ctx, map[string]any{"action": "fit", "model_id": modelID, "X": X, "y": y})
}

func (b *ProcessBridge) Predict(ctx context.Context, modelID string, X []map[string]float64) (*Response, error) {
	return b.request(ctx, map[string]any{"action": "predict", "model_id": modelID, "X": X})
}

func (b *ProcessBridge) Uncertainty(ctx context.Context, modelID string, X []map[string]float64) (*Response, error) {
	return b.request(ctx, map[string]any{"action": "uncertainty", "model_id": modelID, "X": X})
}

func (b *ProcessBridge) Acquisition(ctx context.Context, modelID string, X []map[string]float64, strategy string) (*Response, error) {
	return b.request(ctx, map[string]any{"action": "acquisition", "model_id": modelID, "X": X, "strategy": strategy})
}

func (b *ProcessBridge) Stop() error {
	_, _ = b.request(context.Background(), map[string]any{"action": "stop", "model_id": "stop"})
	_ = b.stdin.Close()
	return b.cmd.Wait()
}

// FakeBridge returns canned responses for offline tests.
type FakeBridge struct {
	FitResponse    *Response
	PredictValues  []float64
	Provenance     *Provenance
	FitError       error
	PredictError   error
	AcquisitionErr error
	Stopped        bool
}

func (f *FakeBridge) Fit(_ context.Context, modelID string, _ []map[string]float64, _ []float64) (*Response, error) {
	if f.FitError != nil {
		return nil, f.FitError
	}
	response := f.FitResponse
	if response == nil {
		response = &Response{OK: true, SchemaVersion: SchemaVersion, Action: "fit", ModelID: modelID}
	}
	return response, nil
}

func (f *FakeBridge) Predict(_ context.Context, modelID string, _ []map[string]float64) (*Response, error) {
	if f.PredictError != nil {
		return nil, f.PredictError
	}
	return &Response{
		OK: true, SchemaVersion: SchemaVersion, Action: "predict", ModelID: modelID,
		Values: f.PredictValues, Provenance: f.Provenance,
	}, nil
}

func (f *FakeBridge) Uncertainty(_ context.Context, modelID string, _ []map[string]float64) (*Response, error) {
	return &Response{
		OK: true, SchemaVersion: SchemaVersion, Action: "uncertainty", ModelID: modelID,
		Values: f.PredictValues, Provenance: f.Provenance,
	}, nil
}

func (f *FakeBridge) Acquisition(_ context.Context, modelID string, _ []map[string]float64, _ string) (*Response, error) {
	if f.AcquisitionErr != nil {
		return nil, f.AcquisitionErr
	}
	return &Response{
		OK: true, SchemaVersion: SchemaVersion, Action: "acquisition", ModelID: modelID,
		Values: f.PredictValues, Provenance: f.Provenance,
	}, nil
}

func (f *FakeBridge) Stop() error {
	f.Stopped = true
	return nil
}
