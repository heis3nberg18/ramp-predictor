Actions are a way for applications to interact with each other and vend UI components for reuse. Think of taking a
picture on your phone and then sharing it to [insert social media platform]. That act of sharing would be an action.

An action is nothing more than a page in an app that expects to be included in an iFrame. When invoked, that iFrame
communicates with its caller using window.postMessage() via the Harmony API. Harmony enforces the shape of the
communication that is sent back and forth from the iFrame by validating the messages against a JSON schema defined for
the action.

To create an Action, you first need to create a new folder with your preferred action name under the `actions` folder.
Within your `action-name` folder, you need create the `metadata.json` file to store the metadata of the action.
`input.json` and `output.json` file contains inputSchema and outputSchema for your Action. To add event(s) to your
Action, create a folder called `events` under your `action-name` folder, inside the `events` folder, your can add
event(s) with the name of the event being the file name. To add command(s) to your Action, create a folder called
`commands` under your `action-name` folder, inside the `commands` folder, your can add command(s) with the name of the
command being the file name. Below, it shows the example of the `actions` folder structure and each sub file structure.

actions folder Example:

    |-- actions
        |-- action-name:
            |-- metadata.json
            |-- input.json
            |-- output.json
            |-- events
                |-- event-name.json
            |-- commands
                |-- command-name.json

metadata.json Example:

    {
        "displayName": "Simple Action Demo",
        "description": "A demo of an action that returns a personalized greeting",
        "src": "demos/simple-demo-action.html",
        "modes": ["interactive", "non-interactive"],
    }

input.json Example:

    {
        "title": "Greeting",
        "description": "How you would like to be greeted",
        "type": "string",
        "default": "Bonjour"
    }

output.json Example:

    {
        "title": "Greeting",
        "description": "A personalized greeting",
        "type": "string"
    }

event-name.json Example:

    {
        "description": "Indicates that the user has selected or unselected an item.",
        "type": "object",
        "properties": {
            "itemId": {
                "description": "The id of the item",
                "type": "string"
            },
            "isSelected": {
                "type": "boolean",
                "description": "True if the item was selected, false if it was unselected"
            }
        }
    }

command-name.json Example:

    {
        "description": "Select or deselect an item.",
        "type": "object",
        "properties": {
            "itemId": {
                "description": "The id of the item",
                "type": "string"
            },
            "isSelected": {
                "type": "boolean",
                "description": "True to mark the item as selected, false to unselect it"
            }
        },
        "required": [
            "itemId",
            "isSelected"
        ]
    }

For more detail information about Actions, please check out our
[docs page](https://console.harmony.a2z.com/docs/actions.html).
