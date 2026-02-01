# HA_enoceanmqtt-addon-ui Development Plan

## Project Overview
Create a Home Assistant addon that provides a user-friendly web interface for configuring EnOcean devices, with special support for Kessel Staufix Control. The UI will visualize the base EEP.xml profiles and allow users to create overrides for custom device configurations.

## Architecture Overview
- **HA Addon**: UI addon with web interface accessible from HA
- **Base EEP.xml**: Included in repository code (updated manually via git)
- **Override System**: JSON-based custom profiles stored in HA config
- **Configuration Storage**: All user configs in HA's `/config/` directory
- **Backup Integration**: HA's backup system includes EnOcean configurations

## Repository Structure
```
HA_enoceanmqtt-addon-ui/
├── addon/
│   ├── config.yaml
│   ├── Dockerfile
│   ├── run.sh
│   └── rootfs/
│       ├── app/
│       │   ├── main.py
│       │   ├── data/
│       │   │   └── base_eep.xml    # Base XML included in code
│       │   ├── xml_manager.py
│       │   ├── override_manager.py
│       │   └── templates/
│       └── static/
├── repository.yaml
├── base_eep.xml                 # Source base XML for updates
└── README.md
```

## Key Components

### 1. Base XML Management
- **Included in Code**: `base_eep.xml` committed to repository
- **Your Updates**: When new base XML available, update via git
- **Version Tracking**: Track base XML version in code
- **Parsing**: Load and parse base XML for profile browsing

### 2. Override System
- **Storage**: JSON overrides in `/config/enocean_overrides/`
- **Format**: Simple JSON for custom profile modifications
- **Merge**: Combine base XML + overrides → final XML
- **Validation**: Ensure overrides are compatible

### 3. Web UI Features
- **Profile Browser**: Browse base profiles with search
- **Override Editor**: Create custom profiles visually
- **Device Manager**: Configure devices with profile selection
- **Export**: Generate final configs for main addon

### 4. Kessel Staufix Support
- **Template**: Pre-built override for A5-30-03
- **Wizard**: Guided setup for Kessel devices
- **Auto-config**: Generate device and mapping files

## User Workflow
1. **Install UI Addon**: Add to HA addon store
2. **Access UI**: Open web interface from HA
3. **Browse Base Profiles**: View included EnOcean profiles
4. **Create Overrides**: Modify for custom devices (Kessel)
5. **Configure Devices**: Set up device IDs and mappings
6. **Export Configuration**: Generate files for main addon
7. **Backup**: HA backup includes all configurations

## Technical Implementation
- **HA Integration**: Web UI accessible via HA interface
- **Config Storage**: All user data in HA's config directory
- **XML Generation**: On-demand creation of final EEP.xml
- **No Downloads**: Everything works offline
- **Version Control**: Base XML updated via your git commits

## Development Phases

### Phase 1: HA Addon Setup
1. Create config.yaml for HA addon store
2. Build Docker container with Python/FastAPI
3. Configure HA ingress for web UI access
4. Set up permissions for HA config directory access

### Phase 2: Base XML Integration
1. Include current base_eep.xml in repository
2. Create XML parser for profile extraction
3. Build searchable profile index
4. Implement profile browsing interface

### Phase 3: Override Management
1. Design JSON override format
2. Implement override CRUD operations
3. Create XML merge engine (base + overrides)
4. Add validation for override compatibility

### Phase 4: Web UI Development
1. Set up FastAPI with Jinja2 templates
2. Create responsive HTML/CSS interface
3. Implement profile browser with search/filter
4. Build override editor forms

### Phase 5: Device Management
1. Create device configuration interface
2. Implement profile selection for devices
3. Add device validation and error handling
4. Generate .devices file format

### Phase 6: Kessel Staufix Integration
1. Create Kessel-specific override template
2. Build guided setup wizard
3. Implement auto-configuration for common settings
4. Add Kessel device recognition

### Phase 7: Export & Integration
1. Generate final EEP.xml from base + overrides
2. Create configuration export functionality
3. Implement import of existing configurations
4. Add configuration backup/restore

## Benefits
- **Offline Operation**: No internet required for configuration
- **Stable Base**: Base XML versioned with your code
- **HA Native**: Integrated configuration experience
- **Automatic Backups**: User configs backed up with HA
- **Maintainable**: You control base XML updates
- **User-Friendly**: Visual configuration instead of XML editing

## Success Criteria
1. Users can browse all EnOcean profiles from base XML
2. Override creation is visual and intuitive
3. Kessel Staufix setup takes <5 minutes
4. Generated configurations work with main addon
5. All user configurations are backed up with HA
6. Interface works on mobile and desktop

## Risk Mitigation
1. **Base XML Updates**: Clear process for updating included XML
2. **Compatibility**: Extensive testing with main addon
3. **User Data**: Safe storage in HA config directory
4. **Performance**: Efficient XML parsing and caching
5. **Security**: Proper HA authentication integration

## Maintenance Strategy
- **Base XML**: Update via git when new versions available
- **User Configs**: Stored in HA, backed up automatically
- **Code Updates**: Standard HA addon update process
- **Documentation**: Comprehensive user guides included

This plan creates a complete configuration ecosystem for EnOcean devices within Home Assistant, making complex device setup accessible to non-technical users while maintaining the power and flexibility needed for advanced configurations.