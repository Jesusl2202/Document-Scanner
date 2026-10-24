# EDA de Semana 2

Documentos en manifiesto: 2712. Desarrollo: 1881.

| Dataset | Campo | Anotados | Total desarrollo | Cobertura |
|---|---|---:|---:|---:|
| sroie | tax_id | 0 | 614 | 0.0% |
| sroie | date | 614 | 614 | 100.0% |
| sroie | document_number | 0 | 614 | 0.0% |
| sroie | subtotal | 0 | 614 | 0.0% |
| sroie | tax | 0 | 614 | 0.0% |
| sroie | total | 613 | 614 | 99.8% |
| wildreceipt | tax_id | 0 | 1267 | 0.0% |
| wildreceipt | date | 1025 | 1267 | 80.9% |
| wildreceipt | document_number | 0 | 1267 | 0.0% |
| wildreceipt | subtotal | 876 | 1267 | 69.1% |
| wildreceipt | tax | 764 | 1267 | 60.3% |
| wildreceipt | total | 1057 | 1267 | 83.4% |

No confundir etiquetas ausentes con campos que el extractor omitió. Casos con varias referencias se excluyen explícitamente hasta revisarlos.
Revisar incidents.csv antes de entrenar o evaluar. Test oficial no se usa para diseñar reglas.