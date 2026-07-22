industrial-knowledge-brain/
├── sample_docs/
│   ├── (your 5 source documents — PDFs, CSVs, PNG)
│   └── extracted/
├── ingestion/
│   ├── schemas.py
│   ├── pdf_parser.py
│   ├── table_parser.py
│   ├── inspection_parser.py
│   ├── drawing_parser.py
│   ├── entity_extractor.py
│   ├── entity_resolution.py
├── graph/
│   ├── load_to_neo4j.py
│   └── verify_tank01_query.py
└── retrieval/
    ├── graph_schema.py
    ├── schema_planner.py
    ├── schema_executor.py
    ├── router.py
    └── test_schema_validation.py