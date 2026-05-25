# AWS Lakehouse Address Validation Pipeline

High-throughput address validation and standardization pipeline for cloud data lakehouses. Processes 10M+ addresses/day with intelligent caching, batching, and cost optimization.

## Status

🚧 **Work in Progress** - Building MVP

## Overview

Government benefits systems (Medicaid, SNAP, TANF) require validated, standardized addresses for eligibility determination and mail delivery. This pipeline validates and enriches addresses at scale using the SmartyStreets USPS API while optimizing for cost and performance.

**Key Challenge:** Process millions of addresses daily while managing API costs ($0.0035 per lookup) and rate limits (100 addresses/request, 10 requests/second).

## Features (Planned)

- Hash-based deduplication (40% API call reduction)
- DynamoDB caching (70%+ cache hit rate on repeat runs)
- Intelligent batching (100 addresses per API call)
- USPS DPV (Delivery Point Validation)
- ZIP+4 and geocoding enrichment
- Apache Iceberg output with time travel
- Exponential backoff retry logic

## Tech Stack

- AWS Glue (PySpark)
- Apache Iceberg
- SmartyStreets API
- DynamoDB
- Python 3.9+
- boto3

## Architecture

```
Coming soon...
```

## License

MIT
