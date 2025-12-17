import streamlit as st
import json
import getpass
from datetime import datetime
import os

# Set page config
st.set_page_config(page_title="Tribal Ideas", page_icon="💡", layout="wide")

# Initialize JSON files if they don't exist
def initialize_json_files():
    # Initialize roles.json
    if not os.path.exists('roles.json'):
        default_roles = {
            "michael": "submitter",
            "alice": "reviewer", 
            "bob": "trainer"
        }
        with open('roles.json', 'w') as f:
            json.dump(default_roles, f, indent=2)
    
    # Initialize ideas.json
    if not os.path.exists('ideas.json'):
        with open('ideas.json', 'w') as f:
            json.dump([], f, indent=2)
    
    # Initialize points.json
    if not os.path.exists('points.json'):
        with open('points.json', 'w') as f:
            json.dump({}, f, indent=2)

def load_json(filename):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except:
        return {} if filename == 'points.json' else []

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def get_current_user():
    return getpass.getuser().lower()

def get_user_role(username):
    roles = load_json('roles.json')
    return roles.get(username, None)

def submitter_page():
    st.header("💡 Submit New Idea")
    
    with st.form("idea_form"):
        idea_text = st.text_area("Enter your idea:", height=150)
        link = st.text_input("Optional link:", placeholder="https://...")
        
        # Tag selection - smooth single field
        predefined_tags = ["UX", "backend", "frontend", "mobile", "AI/ML", "infrastructure", "security", "Custom..."]
        
        selected_tag = st.selectbox("Select tag:", predefined_tags)
        
        if selected_tag == "Custom...":
            tag = st.text_input("Enter custom tag:", placeholder="e.g., analytics, testing, docs, performance...")
        else:
            tag = selected_tag
        
        submitted = st.form_submit_button("Submit Idea")
        
        if submitted:
            if idea_text.strip():
                # Validate tag
                if selected_tag == "Custom..." and not tag.strip():
                    st.error("Please enter a custom tag.")
                    return
                elif not tag:
                    st.error("Please select a tag.")
                    return
                
                ideas = load_json('ideas.json')
                new_idea = {
                    "id": len(ideas) + 1,
                    "text": idea_text.strip(),
                    "link": link.strip() if link.strip() else None,
                    "tag": tag.strip(),
                    "submitter": get_current_user(),
                    "submitted_at": datetime.now().isoformat(),
                    "reviews": [],
                    "trained": False
                }
                ideas.append(new_idea)
                save_json('ideas.json', ideas)
                st.success("✅ Idea submitted successfully!")
                st.rerun()
            else:
                st.error("Please enter an idea text.")

def reviewer_page():
    st.header("🔍 Review Ideas")
    
    ideas = load_json('ideas.json')
    points = load_json('points.json')
    current_user = get_current_user()
    
    # Search functionality
    search_term = st.text_input("🔍 Search ideas:", placeholder="Search by text or tag...")
    
    # Filter ideas based on search
    if search_term:
        filtered_ideas = [idea for idea in ideas if 
                         search_term.lower() in idea['text'].lower() or 
                         search_term.lower() in idea['tag'].lower()]
    else:
        filtered_ideas = ideas
    
    if not filtered_ideas:
        st.info("No ideas found.")
        return
    
    # Display ideas in cards
    for i, idea in enumerate(filtered_ideas):
        with st.expander(f"💡 {idea['tag']} - ID: {idea['id']}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**Idea:** {idea['text']}")
                if idea['link']:
                    st.write(f"**Link:** {idea['link']}")
                st.write(f"**Submitter:** {idea['submitter']}")
                st.write(f"**Submitted:** {idea['submitted_at'][:10]}")
                
                # Show existing reviews
                if idea['reviews']:
                    st.write("**Previous Reviews:**")
                    for review in idea['reviews']:
                        st.write(f"- {review['reviewer']}: {'✅ Accurate' if review['accurate'] else '❌ Not Accurate'}")
            
            with col2:
                # Check if user already reviewed this idea
                user_reviewed = any(review['reviewer'] == current_user for review in idea['reviews'])
                
                if not user_reviewed:
                    col_acc, col_not = st.columns(2)
                    with col_acc:
                        if st.button("✅ Accurate", key=f"acc_{idea['id']}"):
                            # Add review
                            idea['reviews'].append({
                                "reviewer": current_user,
                                "accurate": True,
                                "reviewed_at": datetime.now().isoformat()
                            })
                            # Update points
                            points[current_user] = points.get(current_user, 0) + 5
                            # Save data
                            save_json('ideas.json', ideas)
                            save_json('points.json', points)
                            st.rerun()
                    
                    with col_not:
                        if st.button("❌ Not Accurate", key=f"not_acc_{idea['id']}"):
                            # Add review
                            idea['reviews'].append({
                                "reviewer": current_user,
                                "accurate": False,
                                "reviewed_at": datetime.now().isoformat()
                            })
                            # Update points
                            points[current_user] = points.get(current_user, 0) + 5
                            # Save data
                            save_json('ideas.json', ideas)
                            save_json('points.json', points)
                            st.rerun()
                else:
                    st.success("Already reviewed")

def trainer_page():
    st.header("🎯 Training Management")
    
    ideas = load_json('ideas.json')
    current_user = get_current_user()
    
    # Filter for untraired ideas
    untrained_ideas = [idea for idea in ideas if not idea['trained']]
    
    if not untrained_ideas:
        st.info("All ideas have been trained!")
        return
    
    st.subheader(f"📚 {len(untrained_ideas)} ideas pending training")
    
    for idea in untrained_ideas:
        with st.expander(f"💡 {idea['tag']} - ID: {idea['id']}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**Idea:** {idea['text']}")
                if idea['link']:
                    st.write(f"**Link:** {idea['link']}")
                st.write(f"**Submitter:** {idea['submitter']}")
                st.write(f"**Submitted:** {idea['submitted_at'][:10]}")
                
                # Show reviews
                if idea['reviews']:
                    accurate_count = sum(1 for r in idea['reviews'] if r['accurate'])
                    total_reviews = len(idea['reviews'])
                    st.write(f"**Reviews:** {accurate_count}/{total_reviews} marked as accurate")
            
            with col2:
                if st.button("✅ Mark Trained", key=f"train_{idea['id']}"):
                    # Find and update the idea
                    for i, orig_idea in enumerate(ideas):
                        if orig_idea['id'] == idea['id']:
                            ideas[i]['trained'] = True
                            ideas[i]['trained_by'] = current_user
                            ideas[i]['trained_at'] = datetime.now().isoformat()
                            break
                    save_json('ideas.json', ideas)
                    st.rerun()

def generate_html_report():
    ideas = load_json('ideas.json')
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tribal Ideas Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .tag {{ background-color: #e7f3ff; padding: 2px 6px; border-radius: 3px; }}
            .trained {{ color: green; }}
            .pending {{ color: orange; }}
        </style>
    </head>
    <body>
        <h1>Tribal Ideas Report</h1>
        <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Total Ideas: {len(ideas)}</p>
        
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Tag</th>
                    <th>Idea</th>
                    <th>Link</th>
                    <th>Submitter</th>
                    <th>Submitted</th>
                    <th>Reviews</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for idea in ideas:
        reviews_text = f"{len(idea['reviews'])} reviews"
        if idea['reviews']:
            accurate_count = sum(1 for r in idea['reviews'] if r['accurate'])
            reviews_text += f" ({accurate_count} accurate)"
        
        status = "Trained" if idea['trained'] else "Pending"
        status_class = "trained" if idea['trained'] else "pending"
        
        link_text = f'<a href="{idea["link"]}" target="_blank">Link</a>' if idea.get('link') else 'N/A'
        
        html_content += f"""
                <tr>
                    <td>{idea['id']}</td>
                    <td><span class="tag">{idea['tag']}</span></td>
                    <td>{idea['text']}</td>
                    <td>{link_text}</td>
                    <td>{idea['submitter']}</td>
                    <td>{idea['submitted_at'][:10]}</td>
                    <td>{reviews_text}</td>
                    <td class="{status_class}">{status}</td>
                </tr>
        """
    
    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """
    
    return html_content

def show_leaderboard():
    points = load_json('points.json')
    
    if not points:
        st.info("No points recorded yet.")
        return
    
    st.subheader("🏆 Points Leaderboard")
    
    # Sort by points descending
    sorted_users = sorted(points.items(), key=lambda x: x[1], reverse=True)
    
    for i, (user, user_points) in enumerate(sorted_users):
        if i == 0:
            st.write(f"🥇 **{user}**: {user_points} points")
        elif i == 1:
            st.write(f"🥈 **{user}**: {user_points} points")
        elif i == 2:
            st.write(f"🥉 **{user}**: {user_points} points")
        else:
            st.write(f"   **{user}**: {user_points} points")

def main():
    # Initialize files
    initialize_json_files()
    
    # Get user info
    current_user = get_current_user()
    user_role = get_user_role(current_user)
    
    # Sidebar
    with st.sidebar:
        st.title("🏛️ Tribal Ideas")
        st.write(f"👤 **User:** {current_user}")
        st.write(f"🎭 **Role:** {user_role or 'Unknown'}")
        st.divider()
        
        # Points leaderboard
        show_leaderboard()
        st.divider()
        
        # Download report
        st.subheader("📥 Download Report")
        if st.button("Generate HTML Report"):
            html_content = generate_html_report()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ideas_{timestamp}.html"
            
            # Save to disk first
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            st.download_button(
                label="Download Report",
                data=html_content,
                file_name=filename,
                mime="text/html"
            )
            st.success(f"Report generated: {filename}")
    
    # Main content based on role
    if not user_role:
        st.error("❌ Access denied. User not found in roles.json")
        st.info("Please contact an administrator to add your user to the system.")
        return
    
    if user_role == "admin":
        st.title("🛡️ Admin Dashboard")
        tab1, tab2, tab3 = st.tabs(["💡 Submit Ideas", "🔍 Review Ideas", "🎯 Train Ideas"])
        
        with tab1:
            submitter_page()
        with tab2:
            reviewer_page()
        with tab3:
            trainer_page()
            
    elif user_role == "submitter":
        submitter_page()
    elif user_role == "reviewer":
        reviewer_page()
    elif user_role == "trainer":
        trainer_page()
    else:
        st.error("❌ Unknown role. Please contact an administrator.")

if __name__ == "__main__":
    main()