# NOMAD PERLA PSC Field Map
## Entry-Level Fields (from /entries/query)
| Field Path | Present | Description |
|---|---|---|
| `datasets` | Yes | Associated dataset(s) |
| `entry_id` | Yes | NOMAD entry identifier |
| `entry_name` | Yes | Human-readable entry name |
| `results.material.chemical_formula_reduced` | Yes | Material chemical formula |
| `results.material.structural_type` | Yes | Crystal structure type |
| `results.properties.optoelectronic.solar_cell.device_stack` | Yes | Device stack description |
| `results.properties.optoelectronic.solar_cell.efficiency` | Yes | Power conversion efficiency |
| `results.properties.optoelectronic.solar_cell.fill_factor` | Yes | Fill factor |
| `results.properties.optoelectronic.solar_cell.hole_transport_layer` | Yes | HTL material name |
| `results.properties.optoelectronic.solar_cell.open_circuit_voltage` | Yes | Open circuit voltage (V) |
| `results.properties.optoelectronic.solar_cell.short_circuit_current_density` | Yes | Short circuit current density |
| `upload_id` | Yes | NOMAD upload identifier |

## API Endpoints

- Metadata: `POST /entries/query` (page_size, page_after_value for pagination)
- Archives: `POST /entries/archive/query` (deeper data inspection)
- Base URL: `https://nomad-lab.eu/prod/v1/api/v1`
- No API key required for public data
