# HexaTransit Datasets

## Overview

This repository contains curated datasets for public transportation systems, primarily focused on GTFS (General Transit Feed Specification) data and real-time transit information. The data is used to power transit applications and services, providing up-to-date schedules, routes, and real-time vehicle positions.

## Objectives

- **Centralized Data Management**: Maintain a comprehensive collection of GTFS feeds from various transit agencies
- **Real-time Information**: Provide access to real-time transit updates including vehicle positions, trip updates, and service alerts
- **Data Quality**: Ensure all feeds are validated and accessible through automated checking
- **Continuous Deployment**: Automatically deploy validated datasets to production servers
- **Open Access**: Make transit data easily accessible for developers and transit applications

## Repository Structure

```
.
├── dataset.json          # Static GTFS feed sources
└── realtime.json         # Real-time transit feed updaters
```

## Data Files

### `dataset.json`
Contains static GTFS feed sources with the following structure:
- **type**: Feed type (typically "gtfs")
- **source**: Direct download URL for the GTFS ZIP file
- **feedId**: Unique identifier for the feed
- **reference**: Documentation or information page URL

### `realtime.json`
Contains real-time transit feed updaters compatible with OpenTripPlanner:
- **type**: Updater type (e.g., `stop-time-updater`, `vehicle-positions`, `real-time-alerts`)
- **url**: Real-time API endpoint URL
- **feedId**: Reference to the corresponding static GTFS feed
- **frequency**: Update frequency in seconds (optional)

## 🔍 Coverage

The repository includes transit data from:
- 🇫🇷 France
- 🇯🇵 Japan (real-time)

## ✅ Data Validation

All feeds are automatically validated before deployment using:

### GTFS Feed Checks
- ✓ URL accessibility verification
- ✓ File format validation (ZIP signature detection)
- ✓ Structure validation (required fields)
- ✓ Reference URL validation

### Real-time Feed Checks
- ✓ API endpoint accessibility
- ✓ Response format validation (Protobuf/JSON)
- ✓ Updater type validation
- ✓ Rate limit handling (HTTP 429)
- ✓ No-content handling (HTTP 204)

### Adding New Feeds

1. **For Static GTFS Feeds**: Add to `dataset.json`
```json
{
    "type": "gtfs",
    "source": "https://example.com/gtfs.zip",
    "feedId": "unique-feed-id",
    "reference": "https://example.com/documentation"
}
```

2. **For Real-time Feeds**: Add to `realtime.json`
```json
{
    "type": "stop_time_updater",
    "url": "https://api.example.com/gtfs-rt",
    "feedId": "unique-feed-id",
    "frequency": 30
}
```

3. Create a pull request - automated checks will validate your additions

## 🤝 Contributing

Contributions are welcome! To add new transit feeds:

1. Fork the repository
2. Add your feed(s) to the appropriate JSON file
3. Ensure feeds are publicly accessible
4. Submit a pull request

All contributions will be automatically validated by the CI/CD pipeline.