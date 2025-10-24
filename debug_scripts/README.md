# Debug Scripts Documentation

This folder contains debugging and testing scripts for the Vetri Training Django application.

## Files:

### `check_attendance.py`
- **Purpose**: Quick check of attendance records in database
- **Usage**: `python check_attendance.py`
- **Output**: Shows total attendance count, sample records, and current month stats

### `debug_attendance_detailed.py`
- **Purpose**: Detailed attendance debugging with comprehensive analysis
- **Usage**: `python debug_attendance_detailed.py`
- **Output**: Detailed attendance statistics, patterns, and data validation

### `debug_auth.py`
- **Purpose**: Authentication system debugging
- **Usage**: `python debug_auth.py`
- **Output**: User authentication status, permissions, and login debugging

### `debug_calendar.py`
- **Purpose**: Calendar functionality debugging
- **Usage**: `python debug_calendar.py`
- **Output**: Calendar operations, date handling, and scheduling validation

### `test_user_trainee_relationship.py`
- **Purpose**: Test and validate user-trainee database relationships
- **Usage**: `python test_user_trainee_relationship.py`
- **Output**: Relationship validation, data integrity checks, and user mapping

## Usage Notes:

1. **Setup Required**: All scripts automatically set up Django environment
2. **Database Access**: Requires `db.sqlite3` to be present
3. **Development Only**: These are debugging tools, not production code
4. **Safe to Delete**: Can be removed when no longer needed

## Running Scripts:

```bash
cd /path/to/Vetri-Training-main
python debug_scripts/script_name.py
```

## Organization:
- Keep debug scripts separate from main application code
- Use descriptive names for easy identification
- Document any custom debugging logic
