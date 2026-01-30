---
title: NSW Fuel Check
description: Integration for the New South Wales Fuel Check API
ha_release: 2026.5
ha_iot_class: Cloud Polling
ha_codeowners:
  - '@bicycleboy'
ha_domain: nsw_fuel_ui
ha_integration_type: hub
related:
  - url: https://github.com/bicycleboy/nsw_fuel_ui
    title: Integration Source
  - url: https://https://github.com/bicycleboy/nsw-fuel-api-client
    title: API Client Source
---

The **NSW Fuel Check** {% term integration %} is used to integrate with the NSW Government API for Fuel Prices.   The API supports NSW and Tasmania, Australia (only).


## Prerequisites

1. Visit api.nsw.gov.au.
2. Subscribe to the FuelCheck API (free) and create an app (any name) to obtain your API Key and Secret.
3. Add the Integration entering your API Key and Secret.


## Default Configuration

{% configuration_basic %}
Stations:
    Once you have validated your key and secret you will be prompted to select fuel stations from the list of stations near your home zone. Select one or more stations. Sensors will be created for each station plus 2 additional sensors for the cheapest stations near your home zone.
{% endconfiguration_basic %}

## Configuration options

The integration provides the following configuration options:

{% configuration %}
Nickname:
    description: A name to group your sensors under.  For example Home or Work.  Accept the default or pick a name you like.
    required: false
    type: string
Location:
    description: Use the location selector to choose another location.
    required: false
    type: string
Fuel Type:
    description: Pick a fuel type to create a sensor for.
    required: false
    type: string
{% endconfiguration %}
## Supported functionality

The **NSW Fuel Check** integration provides the following entities.


### Sensors

- **Favorite stations**
  - **Description**: Fuel price for station.
  - **Remarks**: TBA
- **Cheapest Stations**
  - **Description**: Chepest U91 and in NSW E10 near nickname location.
  - **Remarks**: TBA

## Examples
TBA

## Data updates

The **NSW Fuel Check** integration {% term polling polls %} data from the API twiced a day by default.

## Known limitations

The integration currently only supports New South Wales and Tasmania (Australia).
Some fuel types such as EV can be selected but do not return any data.

## Troubleshooting

### Configuring cheapest sensors in the UI

#### Symptom: The fuel price, station name and fuel type cannot be viewed

#### Description

These are additional attributes available in the Tile card and others.

TBC.

#### Resolution

TBA

