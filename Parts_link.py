import streamlit as st
import json
import os
from datetime import datetime

# App configuration
st.set_page_config(page_title="Parts Tracker", layout="wide")

# Database file
PARTS_FILE = "parts.json"

def load_parts():
    """Load parts from JSON file, create empty if doesn't exist"""
    if not os.path.exists(PARTS_FILE):
        with open(PARTS_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    
    try:
        with open(PARTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_parts(parts_data):
    """Save parts to JSON file"""
    with open(PARTS_FILE, 'w') as f:
        json.dump(parts_data, f, indent=2)

def get_query_params():
    """Get query parameters from URL"""
    query_params = st.query_params
    return query_params.get('part', None)

# Load parts data
parts_data = load_parts()

# Check for URL query parameter
url_part = get_query_params()
if url_part and 'selected_part' not in st.session_state:
    st.session_state.selected_part = url_part

# Initialize session state
if 'selected_part' not in st.session_state:
    st.session_state.selected_part = ""
if 'edit_mode' not in st.session_state:
    st.session_state.edit_mode = False

# Sidebar
st.sidebar.header("Part Lookup")

# Get existing parts for dropdown
existing_parts = list(parts_data.keys()) if parts_data else []
existing_parts.sort()

# Create options for selectbox
part_options = [""] + existing_parts + ["➕ Enter new part..."]

# Determine current selection
current_selection = ""
if st.session_state.selected_part:
    if st.session_state.selected_part.upper() in [p.upper() for p in existing_parts]:
        # Find the exact case match
        for part in existing_parts:
            if part.upper() == st.session_state.selected_part.upper():
                current_selection = part
                break
    else:
        current_selection = "➕ Enter new part..."

# Part selection dropdown
selected_option = st.sidebar.selectbox(
    "Select or Enter Part:",
    options=part_options,
    index=part_options.index(current_selection) if current_selection in part_options else 0,
    help="Choose from existing parts or select 'Enter new part' to add a new one"
)

# Handle selection
if selected_option == "➕ Enter new part...":
    # Show text input for new part
    part_input = st.sidebar.text_input(
        "Enter New Part Number:",
        value=st.session_state.selected_part if st.session_state.selected_part not in existing_parts else "",
        placeholder="e.g., ABC123"
    )
    if part_input:
        st.session_state.selected_part = part_input.strip()
    else:
        st.session_state.selected_part = ""
elif selected_option:
    # Use selected existing part
    st.session_state.selected_part = selected_option
else:
    # Empty selection
    st.session_state.selected_part = ""

# Main page
st.title("Parts Tracker")

if st.session_state.selected_part:
    part_number = st.session_state.selected_part.upper()
    
    if part_number in parts_data:
        st.success(f"Part {part_number} found!")
        
        # Get existing data
        current_data = parts_data[part_number]
        
        # Header with edit button
        col1, col2 = st.columns([3, 1])
        with col1:
            st.header(f"Part: {part_number}")
        with col2:
            if st.button("✏️ Edit" if not st.session_state.edit_mode else "❌ Cancel"):
                st.session_state.edit_mode = not st.session_state.edit_mode
                st.rerun()
        
        if st.session_state.edit_mode:
            # Edit mode - show form fields
            st.subheader("Edit Mode")
            
            # Parent dropdown in edit mode
            all_parts = list(parts_data.keys())
            parent_options = [""] + all_parts
            current_parent = current_data.get('parent', '')
            
            parent = st.selectbox(
                "Parent Part:",
                options=parent_options,
                index=parent_options.index(current_parent) if current_parent in parent_options else 0
            )
            
            # Known issues
            issues = st.text_area(
                "Known Issues:",
                value=current_data.get('issues', ''),
                height=100
            )
            
            # Usage
            usage = st.text_area(
                "Usage:",
                value=current_data.get('usage', ''),
                height=100
            )
            
            # Update button
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Save Changes", type="primary"):
                    parts_data[part_number] = {
                        'parent': parent,
                        'issues': issues,
                        'usage': usage
                    }
                    save_parts(parts_data)
                    st.session_state.edit_mode = False
                    st.success("Part updated successfully!")
                    st.rerun()
            with col2:
                if st.button("🔙 Cancel"):
                    st.session_state.edit_mode = False
                    st.rerun()
        
        else:
            # View mode - display data with parent link
            st.subheader("Part Information")
            
            # Parent part with link
            parent_part = current_data.get('parent', '')
            if parent_part:
                if st.button(f"📦 Parent: {parent_part}", help="Click to view parent part"):
                    st.session_state.selected_part = parent_part
                    st.session_state.edit_mode = False
                    st.rerun()
            else:
                st.write("**Parent Part:** _None_")
            
            # Known issues (read-only display)
            issues = current_data.get('issues', '')
            st.write("**Known Issues:**")
            if issues:
                st.text_area("Known Issues Content", value=issues, height=100, disabled=True, label_visibility="collapsed", key=f"issues_view_{part_number}")
            else:
                st.write("_No issues recorded_")
            
            # Usage (read-only display)
            usage = current_data.get('usage', '')
            st.write("**Usage:**")
            if usage:
                st.text_area("Usage Content", value=usage, height=100, disabled=True, label_visibility="collapsed", key=f"usage_view_{part_number}")
            else:
                st.write("_No usage information recorded_")
    
    else:
        st.warning(f"Part {part_number} not found!")
        
        if st.button(f"Add Part {part_number}?"):
            parts_data[part_number] = {
                'parent': '',
                'issues': '',
                'usage': ''
            }
            save_parts(parts_data)
            st.success(f"Part {part_number} added!")
            st.rerun()

else:
    st.info("Enter a part number in the sidebar to get started.")

# Import Parts section
st.header("Import Parts")
import_text = st.text_area(
    "Paste tab-separated data:",
    height=100,
    help="Format: part_number<TAB>parent_part<TAB>known_issues (3rd column optional)"
)

st.info("📋 **Import Format:**\n- 2 columns: `part_number<TAB>parent_part`\n- 3 columns: `part_number<TAB>parent_part<TAB>known_issues`")

if st.button("Import Parts"):
    if import_text.strip():
        lines = import_text.strip().split('\n')
        imported_count = 0
        updated_count = 0
        issues_updated_count = 0
        
        for line in lines:
            if '\t' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    part_num = parts[0].strip().upper()
                    parent_part = parts[1].strip().upper() if parts[1].strip() else ""
                    known_issues = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else ""
                    
                    if part_num in parts_data:
                        # Update existing part
                        part_updated = False
                        
                        # Update parent only if blank
                        if parent_part and not parts_data[part_num].get('parent', ''):
                            parts_data[part_num]['parent'] = parent_part
                            part_updated = True
                        
                        # Update known issues if provided
                        if known_issues:
                            parts_data[part_num]['issues'] = known_issues
                            issues_updated_count += 1
                            part_updated = True
                        
                        if part_updated:
                            updated_count += 1
                    else:
                        # Add new part
                        parts_data[part_num] = {
                            'parent': parent_part,
                            'issues': known_issues,
                            'usage': ''
                        }
                        imported_count += 1
        
        save_parts(parts_data)
        
        # Build success message
        messages = []
        if imported_count > 0:
            messages.append(f"Added {imported_count} new parts")
        if updated_count > 0:
            messages.append(f"updated {updated_count} existing parts")
        if issues_updated_count > 0:
            messages.append(f"updated issues for {issues_updated_count} parts")
        
        success_msg = "Import complete! " + ", ".join(messages) + "."
        st.success(success_msg)
        st.rerun()

# Export Parts section
st.header("Export Parts")

if st.button("Export All Parts to HTML"):
    if parts_data:
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"parts_information_{timestamp}.html"
        
        # Create HTML table with proper escaping
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Parts Information Export - {timestamp}</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 20px; 
            background-color: #f5f5f5; 
        }}
        .container {{ 
            background-color: white; 
            padding: 20px; 
            border-radius: 8px; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        }}
        h1 {{ 
            color: #333; 
            text-align: center; 
            margin-bottom: 30px; 
        }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
            margin: 20px 0; 
        }}
        th, td {{ 
            border: 1px solid #ddd; 
            padding: 12px; 
            text-align: left; 
            vertical-align: top; 
        }}
        th {{ 
            background-color: #4CAF50; 
            color: white; 
            font-weight: bold; 
        }}
        tr:nth-child(even) {{ 
            background-color: #f9f9f9; 
        }}
        tr:hover {{ 
            background-color: #f5f5f5; 
        }}
        .export-info {{ 
            text-align: center; 
            color: #666; 
            margin-bottom: 20px; 
            font-style: italic; 
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Parts Information Export</h1>
        <div class="export-info">
            Generated on: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br>
            Total Parts: {len(parts_data)}
        </div>
        <table>
            <thead>
                <tr>
                    <th>Part Number</th>
                    <th>Parent</th>
                    <th>Known Issues</th>
                    <th>Usage</th>
                </tr>
            </thead>
            <tbody>"""
        
        for part, data in sorted(parts_data.items()):
            # Properly escape HTML content
            parent = data.get('parent', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            issues = data.get('issues', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
            usage = data.get('usage', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
            
            html_content += f"""
                <tr>
                    <td><strong>{part}</strong></td>
                    <td>{parent}</td>
                    <td>{issues}</td>
                    <td>{usage}</td>
                </tr>"""
        
        html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>"""
        
        # Save HTML file locally
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        st.success(f"✅ Exported {len(parts_data)} parts to {filename}")
        
        # Provide download button with the content directly
        st.download_button(
            label="📥 Download HTML File",
            data=html_content,
            file_name=filename,
            mime="text/html",
            help="Click to download the HTML file to your computer"
        )
        
        # Show file location
        st.info(f"📁 File also saved locally as: {filename}")
        
    else:
        st.warning("No parts data to export!")

# Display current parts count
if parts_data:
    st.sidebar.info(f"Total parts in database: {len(parts_data)}")