package nomadperla

import "encoding/json"

// Spec-aligned typed query structures for the NOMAD /entries/query endpoint
// (OpenAPI 3.1.0, NOMAD 1.4.3.post1, server /prod/v1/api/v1).
//
// Pagination fields follow the documented Pagination model: page_size is the
// iteration knob, page_after_value is the documented iteration cursor
// (preferred over page/page_offset by the spec note). OrderBy/Order are
// declared for completeness and left empty by default.

type Pagination struct {
	PageSize       int    `json:"page_size"`
	PageAfterValue string `json:"page_after_value,omitempty"`
	OrderBy        string `json:"order_by,omitempty"`
	Order          string `json:"order,omitempty"`
}

// EntryQuery is the request body for /entries/query. Query holds the
// section/path filters (keys serialized deterministically by json.Marshal).
type EntryQuery struct {
	Owner      string         `json:"owner"`
	Query      map[string]any `json:"query"`
	Pagination Pagination     `json:"pagination"`
}

// BuildHTLSearchQuery constructs the typed HTL search query. Synonyms and
// device architectures keep the same expansion/normalization semantics as the
// previous string builder.
func BuildHTLSearchQuery(htlName string, pageSize int, pageAfterValue string, deviceArchitectures []string) EntryQuery {
	terms := ExpandHTLSynonyms(htlName)
	architectures := normalizedArchitectures(deviceArchitectures)
	query := map[string]any{
		"sections:all": []any{"nomad.datamodel.results.SolarCell"},
		htlQueryPath:   stringSliceAsAny(terms),
	}
	if len(architectures) > 0 {
		query[architecturePath] = stringSliceAsAny(architectures)
	}
	return EntryQuery{
		Owner:      "public",
		Query:      query,
		Pagination: Pagination{PageSize: pageSize, PageAfterValue: pageAfterValue},
	}
}

// Marshal serializes the query body with deterministic key order
// (json.Marshal sorts map keys).
func (q EntryQuery) Marshal() ([]byte, error) {
	return json.Marshal(q)
}
