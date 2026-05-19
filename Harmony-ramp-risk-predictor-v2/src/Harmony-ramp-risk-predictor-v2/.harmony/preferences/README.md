Harmony provides a way for app developers to persist simple configuration specific to their application on a per-user
basis. For example, your app might need to keep track of the current theme chosen by the user, or the last region, or
items that the user has favorited. Although these could be stored in cookies or local storage, by using Harmony's User
Preferences, you can persist these settings across browsers or sessions.

To define a preference, create a JSON file with the preference name under the preferences folder as in the example
below.

preferences folder Example:

    |-- preferences
        |-- background-color.json
        |-- last-region.json
        |-- favorites.json

background-color.json Example:

    {
        "title": "Background Color",
        "description": "Determines the background color of the home page.",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "string",
        "enum": [
            "red",
            "blue",
            "green"
        ]
    }

last-region.json Example:

    {
        "title": "Last Region",
        "description": "Determines the last region of the home page.",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "string",
        "enum": [
            "NA",
            "EU",
            "FE"
        ]
    }

favorites.json Example:

    {
        "description": "Items the user has favorited",
        "preferenceSchema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "description": "Item Id",
                "type": "string"
            }
        }
    }

For more detail information about Preferences, please check out our
[docs page](https://console.harmony.a2z.com/docs/application-development.html#User%20Preferences).
