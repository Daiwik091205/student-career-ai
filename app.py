import streamlit as st
import database as db
import llm_service as llm
import resume_parser
import json

def auth_page():
    st.title("Welcome to Student Career AI")
    st.write("Please log in or register to continue.")

    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_user")
        login_password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if not login_username or not login_password:
                st.error("Please enter both username and password.")
            else:
                user_id = db.verify_user(login_username, login_password)
                if user_id:
                    st.session_state['user_id'] = user_id
                    st.session_state['username'] = login_username
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
                    
    with tab2:
        st.subheader("Register")
        reg_username = st.text_input("Username", key="reg_user")
        reg_password = st.text_input("Password", type="password", key="reg_pass")
        reg_password_confirm = st.text_input("Confirm Password", type="password", key="reg_pass_conf")
        
        if st.button("Register"):
            if not reg_username or not reg_password:
                st.error("Please enter both username and password.")
            elif reg_password != reg_password_confirm:
                st.error("Passwords do not match.")
            else:
                if db.register_user(reg_username, reg_password):
                    st.success("Registration successful! Please log in.")
                else:
                    st.error("Username already exists.")

def render_profile(user_id):
    st.header("My Profile")
    profile = db.get_profile(user_id)
    
    with st.form("profile_form"):
        education = st.text_area("Education", value=profile.get("education", ""), placeholder="e.g., B.S. Computer Science, University of X")
        experience = st.text_area("Experience", value=profile.get("experience", ""), placeholder="e.g., Software Engineering Intern at Company Y")
        interests = st.text_input("Interests", value=profile.get("interests", ""), placeholder="e.g., Machine Learning, Web Development")
        
        if st.form_submit_button("Save Profile"):
            db.save_profile(user_id, education, experience, interests)
            st.success("Profile saved!")

def render_skills_and_projects(user_id):
    st.header("Skills & Projects")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("My Skills")
        skills = db.get_skills(user_id)
        if skills:
            for skill in skills:
                cols = st.columns([3, 1, 1])
                cols[0].write(skill['skill_name'])
                cols[1].write(skill['proficiency'])
                if cols[2].button("X", key=f"del_skill_{skill['id']}"):
                    db.delete_skill(skill['id'])
                    st.rerun()
        else:
            st.info("No skills added yet.")
            
        with st.expander("Add New Skill"):
            new_skill = st.text_input("Skill Name")
            proficiency = st.selectbox("Proficiency", ["Beginner", "Intermediate", "Advanced", "Expert"])
            if st.button("Add Skill"):
                if new_skill:
                    db.add_skill(user_id, new_skill, proficiency)
                    st.rerun()
                    
    with col2:
        st.subheader("My Projects")
        projects = db.get_projects(user_id)
        if projects:
            for p in projects:
                with st.expander(p['project_name']):
                    st.write(p['description'])
                    st.caption(f"Extracted Skills: {p['extracted_skills']}")
                    if st.button("Delete Project", key=f"del_proj_{p['id']}"):
                        db.delete_project(p['id'])
                        st.rerun()
        else:
            st.info("No projects added yet.")
            
        with st.expander("Add New Project & Extract Skills"):
            p_name = st.text_input("Project Name")
            p_desc = st.text_area("Description (Be detailed so AI can extract skills)")
            if st.button("Analyze & Add Project"):
                if p_name and p_desc:
                    with st.spinner("Extracting skills with AI..."):
                        extracted = llm.extract_skills_from_project(p_desc)
                    if extracted.startswith("Error"):
                        st.error(f"Failed to extract skills: {extracted}")
                    else:
                        db.add_project(user_id, p_name, p_desc, extracted)
                        # Automatically add extracted skills to profile as Beginner
                        for s in extracted.split(','):
                            s = s.strip()
                            if s: db.add_skill(user_id, s, "Beginner")
                        st.success("Project added and skills extracted!")
                        st.rerun()

def render_roadmap(user_id):
    st.header("Career Roadmap & Analysis")
    
    # 1. Select Target Career
    career = db.get_latest_target_career(user_id)
    current_career_name = career['career_name'] if career else ""
    
    with st.expander("1. Set Target Career", expanded=not bool(career)):
        new_career = st.text_input("What is your desired job role?", value=current_career_name)
        if st.button("Analyze Career Requirements"):
            if new_career:
                with st.spinner("Analyzing requirements with AI..."):
                    req_skills = llm.analyze_target_career(new_career)
                    db.save_target_career(user_id, new_career, req_skills)
                    st.success("Career analyzed!")
                    st.rerun()
                    
    if career:
        st.info(f"Target Career: **{career['career_name']}**")
        st.caption(f"Required Skills: {career['required_skills']}")
        
        # 2. Gap Analysis & Roadmap Generation
        roadmap_data = db.get_latest_roadmap(user_id)
        
        if st.button("Generate/Update Gap Analysis & Roadmap", type="primary"):
            with st.spinner("Performing Gap Analysis..."):
                skills = db.get_skills(user_id)
                current_skills_str = ", ".join([s['skill_name'] for s in skills])
                
                gap_result = llm.perform_gap_analysis(current_skills_str, career['required_skills'], career['career_name'], st.session_state.get('username', 'the user'))
                gap_analysis = gap_result.get('gap_analysis', '')
                readiness = gap_result.get('readiness_score', 0)
                
            with st.spinner("Generating Personalized Roadmap..."):
                roadmap_json = llm.generate_roadmap(current_skills_str, career['required_skills'], career['career_name'], gap_analysis)
                
            db.save_roadmap(user_id, career['id'], gap_analysis, readiness, json.dumps(roadmap_json))
            st.success("Analysis Complete!")
            st.rerun()
            
        if roadmap_data:
            st.divider()
            col1, col2 = st.columns([1, 2])
            with col1:
                st.metric("Readiness Score", f"{roadmap_data['readiness_score']}%")
            with col2:
                st.subheader("Gap Analysis")
                st.write(roadmap_data['gap_analysis'])
                
            st.subheader("Your Personalized Learning Roadmap")
            for step in roadmap_data['roadmap_json']:
                with st.container(border=True):
                    st.markdown(f"#### Step {step.get('step', '?')}: {step.get('title', 'Untitled')}")
                    st.write(step.get('description', ''))
                    st.caption(f"Skills Covered: {step.get('skills_covered', '')}")
                    if step.get('project_idea'):
                        st.info(f"Project Idea: {step.get('project_idea')}")

def render_resume_and_jobs(user_id):
    st.header("Resume Analysis & Job Recommendations")
    st.write("Upload your resume to get AI-powered job recommendations and an objective gap analysis comparing your profile against market roles.")
    
    profile = db.get_profile(user_id)
    skills = db.get_skills(user_id)
    projects = db.get_projects(user_id)
    
    with st.expander("ℹ️ Profile Data Combined with Resume", expanded=False):
        st.write(f"**Education:** {profile.get('education') or 'Not set'}")
        st.write(f"**Experience:** {profile.get('experience') or 'Not set'}")
        st.write(f"**Interests:** {profile.get('interests') or 'Not set'}")
        st.write(f"**Skills:** {', '.join([s['skill_name'] for s in skills]) if skills else 'None added'}")
        st.write(f"**Saved Projects:** {len(projects)}")
        st.caption("You can update these under the 'Profile' and 'Skills & Projects' tabs anytime.")

    st.subheader("1. Upload Resume")
    uploaded_file = st.file_uploader("Upload your resume (PDF or TXT)", type=["pdf", "txt"], key="resume_uploader")
    
    resume_text = ""
    file_name = ""
    if uploaded_file is not None:
        file_name = uploaded_file.name
        with st.spinner("Extracting text from resume..."):
            extracted_text, err = resume_parser.extract_text_from_file(uploaded_file)
        if err:
            st.error(err)
        else:
            resume_text = extracted_text
            st.success(f"Successfully loaded **{file_name}** ({len(resume_text)} characters extracted).")
            with st.expander("Preview Extracted Resume Content"):
                st.text(resume_text[:2000] + ("..." if len(resume_text) > 2000 else ""))

    # Retrieve existing saved analysis if any
    latest_data = db.get_latest_resume_recommendations(user_id)
    
    st.subheader("2. Run Career Analysis")
    can_analyze = bool(resume_text)
    
    if st.button("Analyze Resume & Generate Job Recommendations", type="primary", disabled=not can_analyze):
        with st.spinner("Analyzing resume and profile for tailored job matches and gaps (rate limited to 5 requests/min)..."):
            username = st.session_state.get('username', 'the user')
            result = llm.analyze_resume_and_recommend_jobs(
                username=username,
                profile_data=profile,
                skills_list=skills,
                projects_list=projects,
                resume_text=resume_text
            )
            
            if result.get("error"):
                st.error(result.get("message", "Analysis request failed due to rate limiting. Please wait a few seconds and try again."))
            else:
                summary = result.get("summary", "")
                recommendations = result.get("recommendations", [])
                
                db.save_resume_recommendations(
                    user_id=user_id,
                    resume_filename=file_name,
                    resume_text=resume_text,
                    summary=summary,
                    recommendations_json=json.dumps(recommendations)
                )
                st.success("Analysis complete!")
                st.rerun()

    if not can_analyze and not latest_data:
        st.info("Please upload a PDF or TXT resume above to begin.")

    # Display results
    if latest_data and not latest_data.get('summary', '').startswith("Error"):
        st.divider()
        st.subheader("Executive Profile Summary")
        if latest_data.get('resume_filename'):
            st.caption(f"Based on resume: `{latest_data['resume_filename']}` (analyzed {latest_data.get('created_at', '')})")
        st.info(latest_data.get('summary', ''))
        
        recs = latest_data.get('recommendations', [])
        if recs:
            st.subheader(f"Recommended Job Roles ({len(recs)})")
            for idx, rec in enumerate(recs, 1):
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"### {idx}. {rec.get('role_title', 'Role')}")
                        st.write(rec.get('why_matched', ''))
                    with col2:
                        score = rec.get('match_score', 0)
                        st.metric("Match Score", f"{score}%")
                    
                    st.divider()
                    col_gaps, col_action = st.columns(2)
                    with col_gaps:
                        st.markdown("##### ⚠️ Gaps to Address")
                        skill_gaps = rec.get('skill_gaps', [])
                        if skill_gaps:
                            st.write("**Technical & Tool Gaps:**")
                            for sg in skill_gaps:
                                st.markdown(f"- {sg}")
                        
                        exp_gaps = rec.get('experience_gaps', [])
                        if exp_gaps:
                            st.write("**Experience & Domain Gaps:**")
                            for eg in exp_gaps:
                                st.markdown(f"- {eg}")
                                
                        if not skill_gaps and not exp_gaps:
                            st.write("No major gaps identified for this role.")
                            
                    with col_action:
                        st.markdown("##### 🎯 Recommended Action Plan")
                        actions = rec.get('action_plan', [])
                        if actions:
                            for act in actions:
                                st.markdown(f"- {act}")
                        else:
                            st.write("No specific actions specified.")
                        
def main():
    st.set_page_config(page_title="AI Career Navigator", layout="wide")
    
    # Initialize DB if not exists
    import os
    if not os.path.exists(db.DB_NAME):
        db.initialize_db()
        
    if 'user_id' not in st.session_state:
        auth_page()
    else:
        with st.sidebar:
            st.write(f"Logged in as: **{st.session_state.get('username')}**")
            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()
                
            st.divider()
            page = st.radio("Navigation", ["Profile", "Skills & Projects", "Roadmap & Analysis", "Resume & Job Match"])
            
        if page == "Profile":
            render_profile(st.session_state['user_id'])
        elif page == "Skills & Projects":
            render_skills_and_projects(st.session_state['user_id'])
        elif page == "Roadmap & Analysis":
            render_roadmap(st.session_state['user_id'])
        elif page == "Resume & Job Match":
            render_resume_and_jobs(st.session_state['user_id'])

if __name__ == "__main__":
    main()
