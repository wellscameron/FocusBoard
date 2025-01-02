import streamlit as st
import os
import json
import markdown
from datetime import datetime
from pathlib import Path
import shutil
import base64
from yt_dlp import YoutubeDL
import google.generativeai as genai  # Add this import
import time  # Add this import
from user_auth import UserAuth

# Add Gemini setup
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])  # Replace this with your Gemini API key

class ProjectDashboard:
    def __init__(self):
        self.data_dir = Path("project_data")
        self.data_dir.mkdir(exist_ok=True)
        
    def save_project(self, project_name, data):
        # Add IDs to todos if they don't have one
        for todo in data["todos"]:
            if "id" not in todo:
                todo["id"] = str(datetime.now().timestamp())
        
        project_dir = self.data_dir / project_name
        project_dir.mkdir(exist_ok=True)
        
        # Create attachments directory if it doesn't exist
        attachments_dir = project_dir / "attachments"
        attachments_dir.mkdir(exist_ok=True)
        
        with open(project_dir / "project_info.json", "w") as f:
            json.dump(data, f, indent=4)
    
    def save_attachment(self, project_name, file):
        project_dir = self.data_dir / project_name / "attachments"
        file_path = project_dir / file.name
        with open(file_path, "wb") as f:
            f.write(file.getvalue())
        return str(file_path)
    
    def get_attachment(self, file_path):
        with open(file_path, "rb") as f:
            return f.read()
    
    def archive_project(self, project_name):
        source_dir = self.data_dir / project_name
        archive_dir = self.data_dir / "archived" / project_name
        archive_dir.parent.mkdir(exist_ok=True)
        shutil.move(str(source_dir), str(archive_dir))
    
    def load_project(self, project_name):
        project_dir = self.data_dir / project_name
        project_file = project_dir / "project_info.json"
        
        if not project_file.exists():
            return None
        
        try:
            with open(project_file, "r") as f:
                return json.load(f)
        except:
            return None
    
    def get_projects(self):
        # Only return projects that have valid project_info.json files
        projects = []
        for d in self.data_dir.iterdir():
            if d.is_dir() and d.name != "archived":
                if (d / "project_info.json").exists():
                    projects.append(d.name)
        return projects
    
    def calculate_days_until_due(self, due_date):
        if not due_date:
            return None
        due = datetime.strptime(due_date, "%Y-%m-%d")
        days = (due - datetime.now()).days
        return days

def init_session_state():
    if "categories" not in st.session_state:
        st.session_state.categories = [
            "Personal", "Work", "Education", "Health", "Finance", "Other"
        ]
    if "show_manage_page" not in st.session_state:
        st.session_state.show_manage_page = False

def show_login_page():
    st.title("FocusBoard")
    st.subheader("Your personal productivity hub")
    
    auth = UserAuth()
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                success, message = auth.login_user(username, password)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Register")
            
            if submit:
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    success, message = auth.register_user(new_username, new_password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

# Add this new function to handle the manage projects page
def show_manage_projects_page(dashboard):
    st.title("Manage Projects")
    
    projects = dashboard.get_projects()
    if not projects:
        st.info("No projects found.")
        return
        
    # Create a card-like display for each project
    for project in projects:
        project_data = dashboard.load_project(project)
        if not project_data:
            continue
            
        with st.expander(f"📁 {project}", expanded=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown(f"**Category:** {project_data.get('category', 'N/A')}")
                st.markdown(f"**Created:** {project_data.get('created_date', 'N/A')}")
                
                # Due date editor
                current_due = datetime.strptime(project_data['due_date'], "%Y-%m-%d") if project_data.get('due_date') else None
                new_due_date = st.date_input(
                    "Due Date",
                    value=current_due,
                    min_value=datetime.now().date() if not current_due else None,
                    key=f"due_date_{project}"
                )
                
                if new_due_date and (not current_due or new_due_date.strftime("%Y-%m-%d") != project_data['due_date']):
                    project_data['due_date'] = new_due_date.strftime("%Y-%m-%d")
                    dashboard.save_project(project, project_data)
                    st.success("Due date updated!")
            
            with col2:
                # Project statistics
                total_tasks = len(project_data.get('todos', []))
                completed_tasks = len([t for t in project_data.get('todos', []) if t.get('completed')])
                total_docs = len(project_data.get('documents', []))
                
                st.markdown(f"**Tasks:** {completed_tasks}/{total_tasks} completed")
                st.markdown(f"**Documents:** {total_docs}")
                
                # Days until due
                if project_data.get('due_date'):
                    days_until_due = dashboard.calculate_days_until_due(project_data['due_date'])
                    if days_until_due is not None:
                        due_text = (f"**{days_until_due} days** until due" if days_until_due > 0 
                                  else "**Due today!**" if days_until_due == 0 
                                  else f"**{abs(days_until_due)} days overdue**")
                        st.markdown(due_text)
            
            with col3:
                # Delete project button
                if st.button("🗑️ Delete Project", key=f"delete_{project}"):
                    if "confirm_delete" not in st.session_state:
                        st.session_state.confirm_delete = {}
                    st.session_state.confirm_delete[project] = True
                    st.rerun()
                
                # Show confirmation
                if st.session_state.get("confirm_delete", {}).get(project):
                    st.warning("Are you sure? This cannot be undone!")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Yes, delete", key=f"confirm_{project}"):
                            try:
                                # Delete project directory and all contents
                                project_dir = dashboard.data_dir / project
                                if project_dir.exists():
                                    # First, try to remove any read-only attributes
                                    for root, dirs, files in os.walk(str(project_dir)):
                                        for dir_name in dirs:
                                            dir_path = Path(root) / dir_name
                                            try:
                                                os.chmod(str(dir_path), 0o777)
                                            except:
                                                pass
                                        for file_name in files:
                                            file_path = Path(root) / file_name
                                            try:
                                                os.chmod(str(file_path), 0o777)
                                            except:
                                                pass
                                    
                                    # Then try to remove the directory
                                    shutil.rmtree(project_dir, ignore_errors=True)
                                    
                                    # Verify if deletion was successful
                                    if project_dir.exists():
                                        st.error("Could not fully delete the project. Some files may be in use.")
                                    else:
                                        st.success("Project deleted successfully!")
                                
                                # Clear confirmation state
                                st.session_state.confirm_delete[project] = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting project: {str(e)}")
                    with col2:
                        if st.button("Cancel", key=f"cancel_{project}"):
                            st.session_state.confirm_delete[project] = False
                            st.rerun()

def main():
    st.set_page_config(page_title="FocusBoard", layout="wide")
    init_session_state()
    
    # Initialize login state if not exists
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    
    if not st.session_state.logged_in:
        show_login_page()
        return
    
    dashboard = ProjectDashboard()
    
    # Sidebar navigation
    with st.sidebar:
            if st.session_state.get("show_manage_page"):
                if st.button("Home", key="home_button"):
                    st.session_state.show_manage_page = False
                    st.rerun()
            else:
                st.header("Create a New Project")
                new_project = st.text_input("New Project Name")
                
                # Add due date input
                due_date = st.date_input(
                    "Due Date (optional)",
                    value=None,
                    min_value=datetime.now().date(),
                    help="Leave empty if no due date"
                )
                
                # Project category selection
                category = st.selectbox(
                    "Project Category",
                    st.session_state.categories
                )
                
                if st.button("Create Project"):
                    if new_project:
                        project_data = {
                            "name": new_project,
                            "category": category,
                            "created_date": datetime.now().strftime("%Y-%m-%d"),
                            "due_date": due_date.strftime("%Y-%m-%d") if due_date else None,
                            "todos": [],
                            "documents": [],
                            "archived": False
                        }
                        dashboard.save_project(new_project, project_data)
                        st.success(f"Created project: {new_project}")
                
                # Project filtering
                st.divider()
                st.header("My Projects")
                
                # Add Manage Projects button with unique key
                if st.button("Manage Projects", key="manage_projects_button"):
                    st.session_state.show_manage_page = True
                    st.rerun()
                
                filter_category = st.selectbox(
                    "Filter by Category",
                    ["All"] + st.session_state.categories
                )
                
                projects = dashboard.get_projects()
                if filter_category != "All":
                    filtered_projects = []
                    for project in projects:
                        data = dashboard.load_project(project)
                        if data and data.get("category") == filter_category:
                            filtered_projects.append(project)
                    projects = filtered_projects
                
                selected_project = st.selectbox(
                    "Select Project",
                    projects if projects else ["No projects yet"]
                )

                st.markdown("---")

            # Logout button at bottom
            if st.button("Logout", key="logout_button"):
                st.session_state.logged_in = False
                st.rerun()

    # Main content area
    if st.session_state.get("show_manage_page"):
        show_manage_projects_page(dashboard)
    else:
        if selected_project and selected_project != "No projects yet":
            project_data = dashboard.load_project(selected_project)
            
            # Set the title with project name
            st.title(f"{project_data['name']}: Project Dashboard")
            
            # Add due date info if exists
            if project_data.get("due_date"):
                days_until_due = dashboard.calculate_days_until_due(project_data["due_date"])
                if days_until_due is not None:
                    due_text = f"{days_until_due} days until project is due" if days_until_due > 0 else "Project is due today!" if days_until_due == 0 else "Project is overdue"
                    st.markdown(f"<p style='color: gray; font-size: 14px;'>{due_text}</p>", unsafe_allow_html=True)
            
            # Main content area - three columns
            col1, col2, col3 = st.columns(3)
            
            # To-do list management in first column
            with col1:
                st.header("To-Do List")
                new_todo = st.text_input("New Task")
                if st.button("Add Task"):
                    if new_todo:
                        project_data["todos"].append({
                            "id": str(datetime.now().timestamp()),
                            "task": new_todo,
                            "completed": False,
                            "date_added": datetime.now().strftime("%Y-%m-%d")
                        })
                        dashboard.save_project(selected_project, project_data)
                
                # Add clear completed tasks button
                if project_data["todos"]:
                    if st.button("Clear Completed Tasks"):
                        project_data["todos"] = [todo for todo in project_data["todos"] if not todo["completed"]]
                        dashboard.save_project(selected_project, project_data)
                        st.rerun()
                
                for todo in project_data["todos"]:
                    col_check, col_task, col_delete = st.columns([0.5, 4, 0.5])
                    with col_check:
                        checked = st.checkbox("", todo["completed"], key=f"todo_{todo['id']}")
                        if checked != todo["completed"]:
                            todo["completed"] = checked
                            dashboard.save_project(selected_project, project_data)
                    with col_task:
                        st.markdown(f"""
                            <div style='display: flex; align-items: center; min-height: 40px; padding-left: 10px;'>
                                {todo['task']}
                            </div>
                        """, unsafe_allow_html=True)
                    with col_delete:
                        if st.button("×", key=f"delete_todo_{todo['id']}", type="secondary", help="Delete task"):
                            project_data["todos"].remove(todo)
                            dashboard.save_project(selected_project, project_data)
                            st.rerun()
            
            # Document management in second column
            with col2:
                st.header("Documents")
                doc_title = st.text_input("Document Title")
                
                # Markdown editor with preview
                doc_content = st.text_area("Document Content (Markdown supported)", height=200)
                if doc_content:
                    st.markdown("Preview:")
                    st.markdown(doc_content)
                
                # File attachment
                uploaded_file = st.file_uploader("Attach File", type=['pdf', 'txt', 'png', 'jpg', 'jpeg'])
                
                if st.button("Save Document"):
                    if doc_title and (doc_content or uploaded_file):
                        attachment_path = None
                        if uploaded_file:
                            attachment_path = dashboard.save_attachment(selected_project, uploaded_file)
                        
                        project_data["documents"].append({
                            "title": doc_title,
                            "content": doc_content,
                            "date_created": datetime.now().strftime("%Y-%m-%d"),
                            "attachment": attachment_path
                        })
                        dashboard.save_project(selected_project, project_data)
                
                # Display documents with attachments
                for i, doc in enumerate(project_data["documents"]):
                    col_doc, col_del = st.columns([4, 1])
                    with col_doc:
                        with st.expander(f"{doc['title']} ({doc['date_created']})"):
                            st.markdown(doc["content"])
                            if doc.get("attachment"):
                                file_path = doc["attachment"]
                                file_name = Path(file_path).name
                                with open(file_path, "rb") as f:
                                    st.download_button(
                                        f"Download {file_name}",
                                        f,
                                        file_name=file_name
                                    )
                    with col_del:
                        if st.button("×", key=f"delete_doc_{i}", type="secondary", help="Delete document"):
                            project_data["documents"].pop(i)
                            dashboard.save_project(selected_project, project_data)
                            st.rerun()
            
            # YouTube video processor in third column
            with col3:
                st.header("Video Notes")
                url = st.text_input("Enter YouTube URL")
                if url:
                    try:
                        # Create a status placeholder for user feedback
                        status_placeholder = st.empty()
                        status_placeholder.info("Starting video processing...")

                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                ydl_opts = {
                                    'writesubtitles': True,
                                    'writeautomaticsub': True,
                                    'subtitlesformat': 'json3',
                                    'skip_download': True,
                                    'quiet': True,
                                    'no_warnings': True
                                }
                                
                                with YoutubeDL(ydl_opts) as ydl:
                                    # Get video info and subtitles
                                    status_placeholder.info("🔍 Fetching video information and captions...")
                                    info = ydl.extract_info(url, download=False)
                                    video_title = info.get('title', 'Untitled Video')
                                    
                                    # Get automatic captions if available
                                    status_placeholder.info("🔍 Fetching video captions...")
                                    
                                    transcription_text = ""
                                    if info.get('subtitles'):
                                        captions = info['subtitles'].get('en', [])
                                    elif info.get('automatic_captions'):
                                        captions = info['automatic_captions'].get('en', [])
                                    
                                    if captions:
                                        for caption in captions:
                                            if caption.get('ext') == 'json3':
                                                caption_url = caption.get('url')
                                                if caption_url:
                                                    import requests
                                                    response = requests.get(caption_url)
                                                    if response.status_code == 200:
                                                        caption_data = response.json()
                                                        for event in caption_data.get('events', []):
                                                            if 'segs' in event:
                                                                for seg in event['segs']:
                                                                    transcription_text += seg.get('utf8', '') + " "
                                    
                                    if not transcription_text.strip():
                                        raise Exception("Could not extract captions from the video.")

                                    # Generate summary using Gemini
                                    status_placeholder.info("📝 Generating summary...")
                                    
                                    # Configure the model
                                    model = genai.GenerativeModel('gemini-1.5-flash-latest')
                                    
                                    # Generate the summary
                                    prompt = f"""Please provide a concise summary of the following text:
                                    
                                    {transcription_text}
                                    
                                    Focus on the main points and key takeaways. If I have not provided any text, please print an error message."""
                                    
                                    response = model.generate_content(prompt)
                                    
                                    # Save to project documents
                                    status_placeholder.info("💾 Saving to project documents...")
                                    project_data["documents"].append({
                                        "title": f"Video Notes: {video_title}",
                                        "content": f"""## Video Summary\n\n{response.text}""",
                                        "date_created": datetime.now().strftime("%Y-%m-%d"),
                                        "type": "video_notes"
                                    })
                                    dashboard.save_project(selected_project, project_data)
                                    
                                    status_placeholder.success("✨ Video processed and notes saved successfully!")
                                    break

                            except Exception as e:
                                if attempt == max_retries - 1:
                                    raise Exception(f"Failed to process video after {max_retries} attempts: {str(e)}")
                                time.sleep(2)

                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
                        st.info("If you're seeing an error, try these troubleshooting steps:\n"
                               "1. Verify the video is publicly accessible\n"
                               "2. Check if the video has captions available\n"
                               "3. Check if the video URL is correct")
                
                st.markdown("""
                    Add video notes to your project by:
                    1. Paste a YouTube URL
                    2. Wait for processing (This may take a few minutes)
                    3. Notes will be saved in your documents
                """)
        else:
            # Show "Project Dashboard" only when no project is selected
            st.title("Project Dashboard")
            st.markdown("""
                **No Project Selected**
                
                To get started:
                1. Create a new project using the sidebar form
                2. Or select an existing project from the dropdown menu
            """)

if __name__ == "__main__":
    main()
