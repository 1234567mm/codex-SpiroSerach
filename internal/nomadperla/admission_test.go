package nomadperla

import (
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"testing"

	"spirosearch/internal/providercache"
)

func TestBuildNomadAdmissionPlanDefaultsToPositiveSpiroNipQuery(t *testing.T) {
	provider := ProviderName
	plan, err := BuildNomadAdmissionPlan(AdmissionTask{
		ActionType:    "start_nomad_sync",
		Provider:      &provider,
		ProviderScope: "source",
	})
	if err != nil {
		t.Fatalf("BuildNomadAdmissionPlan() error = %v", err)
	}

	if plan.SchemaVersion != NomadAdmissionPlanSchemaVersion ||
		plan.Provider != ProviderName ||
		plan.Endpoint != "/entries/query" ||
		plan.Owner != "public" ||
		plan.DeviceArchitecture != "nip" ||
		plan.MaxPageSize != 25 ||
		plan.MaxPages != 1 ||
		plan.LiveCallsAuthorized {
		t.Fatalf("plan defaults drifted: %#v", plan)
	}
	if !reflect.DeepEqual(plan.HTLAliases, []string{"Spiro-OMeTAD"}) {
		t.Fatalf("HTL aliases = %#v", plan.HTLAliases)
	}

	expectedSearchBody := map[string]any{
		"owner": "public",
		"query": map[string]any{
			"sections:all": []any{"nomad.datamodel.results.SolarCell"},
			htlQueryPath:   []any{"Spiro-OMeTAD"},
			architecturePath: []any{
				"nip",
			},
		},
		"pagination": map[string]any{"page_size": 25},
	}
	if !reflect.DeepEqual(plan.SearchBody, expectedSearchBody) {
		t.Fatalf("search body mismatch:\nactual: %#v\nwant: %#v", plan.SearchBody, expectedSearchBody)
	}
	expectedHash, err := providercache.StableHash(expectedSearchBody)
	if err != nil {
		t.Fatal(err)
	}
	if plan.SearchQueryHash != expectedHash {
		t.Fatalf("search query hash = %s, want %s", plan.SearchQueryHash, expectedHash)
	}
	if plan.ArchiveRequiredTreeHash != ArchiveRequiredTreeHash() {
		t.Fatalf("archive required tree hash = %s", plan.ArchiveRequiredTreeHash)
	}
}

func TestBuildNomadAdmissionPlanAllowsOnlyPositiveArchitectures(t *testing.T) {
	for _, architecture := range []string{"nip", "pin"} {
		t.Run(architecture, func(t *testing.T) {
			plan, err := BuildNomadAdmissionPlan(AdmissionTask{
				ActionType:         "start_nomad_sync",
				ProviderScope:      "source",
				DeviceArchitecture: architecture,
			})
			if err != nil {
				t.Fatalf("BuildNomadAdmissionPlan() error = %v", err)
			}
			if plan.DeviceArchitecture != architecture {
				t.Fatalf("architecture = %s", plan.DeviceArchitecture)
			}
		})
	}

	for _, architecture := range []string{"mesoscopic", "NIP", " nip "} {
		t.Run(architecture, func(t *testing.T) {
			if _, err := BuildNomadAdmissionPlan(AdmissionTask{
				ActionType:         "start_nomad_sync",
				ProviderScope:      "source",
				DeviceArchitecture: architecture,
			}); err == nil {
				t.Fatalf("expected architecture %q to fail closed", architecture)
			}
		})
	}
}

func TestBuildNomadAdmissionPlanRejectsNonNomadAdmissionTasks(t *testing.T) {
	provider := "materials_project"
	for _, task := range []AdmissionTask{
		{ActionType: "pause_nomad_sync", ProviderScope: "source"},
		{ActionType: "start_nomad_sync", Provider: &provider, ProviderScope: "source"},
		{ActionType: "start_nomad_sync", ProviderScope: "model"},
	} {
		if _, err := BuildNomadAdmissionPlan(task); err == nil {
			t.Fatalf("expected task to be rejected: %#v", task)
		}
	}
}

func TestNomadAdmissionPlanIsHashableAndDoesNotConstructTransport(t *testing.T) {
	plan, err := BuildNomadAdmissionPlan(AdmissionTask{
		ActionType:    "start_nomad_sync",
		ProviderScope: "source",
	})
	if err != nil {
		t.Fatal(err)
	}
	planMap := plan.ToMap()
	raw, err := json.Marshal(planMap)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), "http://") ||
		strings.Contains(string(raw), "https://") ||
		strings.Contains(string(raw), "Bearer ") {
		t.Fatalf("admission plan must not contain transport or credential values: %s", raw)
	}
	if plan.LiveCallsAuthorized {
		t.Fatal("admission plan must not authorize live calls")
	}
	if _, err := providercache.StableHash(planMap); err != nil {
		t.Fatalf("plan is not stable-hashable: %v", err)
	}

	source, err := os.ReadFile("admission.go")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(source), "http.Client") ||
		strings.Contains(string(source), "http.NewRequest") ||
		strings.Contains(string(source), "Transport") ||
		strings.Contains(string(source), "PostJSON") {
		t.Fatalf("admission planner must not construct provider transport")
	}
}
