package workflowtask

type Definition struct {
	Provider        *string
	ProviderScope   string
	DeclaredEffects []string
}

var workflowDefinitions = map[string]Definition{
	"start_nomad_sync":                      {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"pause_nomad_sync":                      {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"resume_nomad_sync":                     {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"cancel_nomad_sync":                     {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"import_doi_list":                       {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"paper_sources", "manual_acquisition_tasks"}},
	"import_paper_group":                    {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"paper_groups", "paper_assets"}},
	"import_hopv15_snapshot":                {Provider: ptr("hopv15"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"import_opv_db_snapshot":                {Provider: ptr("opv_db"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"import_pubchemqc_snapshot":             {Provider: ptr("pubchemqc"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"import_materials_cloud_archive_record": {Provider: ptr("materials_cloud"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"refresh_pubchem_identity_cache":        {Provider: ptr("pubchem"), ProviderScope: "source", DeclaredEffects: []string{"provider_cache"}},
	"run_parsing_job":                       {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"knowledge_chunks"}},
	"run_extraction_job":                    {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"extracted_claims", "citation_links"}},
	"run_htl_screening":                     {Provider: nil, ProviderScope: "local", DeclaredEffects: []string{"screening_result"}},
}

var Definitions = definitionsSnapshot()

func DefinitionFor(actionType string) (Definition, bool) {
	definition, ok := workflowDefinitions[actionType]
	if !ok {
		return Definition{}, false
	}
	return Definition{
		Provider:        copyStringPointer(definition.Provider),
		ProviderScope:   definition.ProviderScope,
		DeclaredEffects: append([]string(nil), definition.DeclaredEffects...),
	}, true
}

func definitionsSnapshot() map[string]Definition {
	result := make(map[string]Definition, len(workflowDefinitions))
	for actionType := range workflowDefinitions {
		definition, _ := DefinitionFor(actionType)
		result[actionType] = definition
	}
	return result
}

func ptr(value string) *string {
	return &value
}
