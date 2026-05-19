# Gold Outreach - MS Outlook Plugin

A full-featured MS Outlook plugin for automating email campaigns with support for campaign management, reply tracking, and conversion analytics.

## Architecture

The application is built on a **Layered Event-Driven Modular Architecture**:

- **Presentation Layer** (`src/presentation/`) - GUI components built with tkinter
- **Application Layer** (`src/application/`) - business logic, use cases, event bus, plugin system
- **Domain Layer** (`src/domain/`) - domain models and events
- **Infrastructure Layer** (`src/infrastructure/`) - implementations for working with YAML, CSV, TOML, and Outlook

## Features

### Core Functionality

- ✅ Load variables from YAML or CSV files
- ✅ Load email templates from YAML or TOML files
- ✅ Automatic variable substitution in templates (format: `{{variable_name}}`)
- ✅ Create mailing campaigns
- ✅ Bulk email sending via Outlook (simulating manual sending)
- ✅ Reply tracking for sent emails
- ✅ Conversion rate calculation per campaign
- ✅ GUI interface built with tkinter and dialog windows
- ✅ Event-driven architecture for operation tracking
- ✅ Modular plugin system

### Outlook Plugin

- ✅ Integration with MS Outlook via the Ribbon panel
- ✅ Minimal VBA usage (only for invoking Python)
- ✅ Dedicated "Gold Outreach" tab in the Outlook management panel

## Requirements

- Python 3.8+
- Windows (required for MS Outlook)
- MS Outlook installed and configured
- pywin32 for working with the Outlook COM interface

## Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

**Note:** On Windows, you must also install pywin32 to work with the Outlook COM interface.

2. To install the plugin into Outlook:

   - Copy the files from `outlook_addin/` into the Outlook macros folder
   - Set the path to the Python script in `RibbonHandler.bas` (constant `PYTHON_SCRIPT_PATH`)
   - Enable macros in Outlook (File → Options → Trust Center → Trust Center Settings → Macros)

## Usage

### Running as a Standalone Application

```bash
python main.py
```

### Using as an Outlook Plugin

1. Open Outlook
2. Navigate to the "Gold Outreach" tab in the Ribbon panel
3. Use the buttons to manage campaigns

### Creating a Campaign

1. Prepare a CSV file with recipients (see example in `config/example_recipients.csv`)
2. Prepare an email template in YAML or TOML (see examples in `config/`)
3. In the application:
   - Click "Create campaign"
   - Select a template
   - Select the CSV file with recipients
   - Click "Create"

### Starting a Campaign

1. Open "Campaign Management"
2. Select a campaign
3. Click "Start"
4. Emails will be sent with a delay between each one (simulating manual sending)

### Tracking Replies

1. In "Campaign Management", select a campaign
2. Click "Check replies"
3. The system will automatically find replies and update the statistics

## File Formats

### CSV File with Recipients

```csv
email,name,company,position
ivan@example.com,Ivan Ivanov,Example LLC,Director
petr@example.com,Petr Petrov,Other LLC,Manager
```

Each row represents one recipient. Columns can be anything — they become variables for substitution in the template.

### Variables File (variables.yaml)

```yaml
company_name: "Example LLC"
contact_person: "Ivan Ivanov"
email: "ivan@example.com"
```

### Templates File (templates.yaml or templates.toml)

```yaml
template_name:
  subject: "Email subject with {{variable_name}}"
  body: |
    Email body
    You can use {{variable_name}} for substitution
  recipient: "{{email}}"  # optional, can also be specified in CSV
```

Variables in templates use the format `{{variable_name}}` and are automatically replaced with values from CSV or YAML.

## Plugin System

The application supports a modular plugin system. Create a file in the `plugins/` folder that inherits from the `Plugin` class:

```python
from src.application.plugin_system import Plugin
from src.domain.events import Event

class MyPlugin(Plugin):
    def initialize(self):
        # Plugin initialization
        pass
    
    def handle_event(self, event: Event):
        # Handle events
        if event.event_type == "email_sent":
            # Your logic here
            pass
```

Plugins are automatically loaded at application startup.

## Project Structure

```
gold-outreach/
├── src/
│   ├── domain/              # Domain layer
│   │   ├── events.py       # Events
│   │   └── models.py       # Domain models (Email, Campaign, etc.)
│   ├── application/        # Application layer
│   │   ├── event_bus.py    # Event bus
│   │   ├── email_service.py    # Service for working with emails
│   │   ├── campaign_service.py # Service for managing campaigns
│   │   └── plugin_system.py    # Plugin system
│   ├── infrastructure/     # Infrastructure layer
│   │   ├── yaml_loader.py      # YAML loader
│   │   ├── csv_loader.py       # CSV loader
│   │   ├── toml_loader.py      # TOML loader
│   │   └── outlook_client.py   # Outlook client
│   └── presentation/       # Presentation layer
│       ├── main_window.py      # Main window
│       ├── campaign_dialog.py  # Campaign dialog
│       └── log_dialog.py       # Log dialog
├── outlook_addin/          # Outlook plugin files
│   ├── customUI.xml        # Ribbon XML
│   ├── RibbonHandler.bas   # VBA handlers
│   └── ThisAddIn.cls       # VBA class
├── plugins/                # Plugins
│   └── example_plugin.py   # Example plugin
├── config/                 # Example configuration files
├── outlook_launcher.py     # Launcher for the Outlook plugin
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
└── README.md              # Documentation
```

## Event-Driven Architecture

The application uses an event-driven approach:

- **EventBus** - centralized event bus
- **Events**:
  - `VariablesLoadedEvent` - variables loaded
  - `TemplatesLoadedEvent` - templates loaded
  - `CampaignCreatedEvent` - campaign created
  - `CampaignStartedEvent` - campaign started
  - `EmailSentEvent` - email sent
  - `EmailRepliedEvent` - reply received on email
  - `CampaignCompletedEvent` - campaign completed
  - `ErrorEvent` - errors

All events are published through the EventBus and handled by subscribed handlers (GUI, plugins).

## Metrics and Conversions

The system automatically tracks:
- Number of sent emails
- Number of received replies
- Conversion rate per campaign (percentage of replies)
- Campaign completion percentage

## Notes

- The application runs only on Windows due to its dependency on MS Outlook
- Ensure Outlook is installed and configured before use
- Emails are sent with delays to simulate manual sending by a salesperson
- The system tracks only replies (not email opens)
- Emails appear as if sent manually by a salesperson

## License

MIT
