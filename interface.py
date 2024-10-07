

import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas as pd
import psycopg2
import random
import numpy as np
import autoschedulemodule 

st.set_page_config(layout="wide")

db_params = {
    'dbname': 'courses_n_sessions',
    'user': 'ansarantayev',
    'password': 'ansar111',
    'host': 'localhost',
    'port': 5432
}

def get_course_suggestions(prefix):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT COURSE_NAME FROM COURSES WHERE COURSE_NAME ILIKE %s", (f"{prefix}%",))
    courses = [row[0] for row in cursor.fetchall()]
    conn.close()
    return courses

def get_all_professors():
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT PROFESSOR FROM SESSIONS")
    professors = [row[0] for row in cursor.fetchall()]
    conn.close()
    return professors

def get_sessions_for_courses(courses, excluded_profs):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    format_strings = ','.join(['%s'] * len(courses))
    query = f"""
        SELECT SESSION_ID, COURSE_NAME, SESSION_NAME, TIME
        FROM SESSIONS
        WHERE COURSE_NAME IN ({format_strings})
    """
    params = courses
    if excluded_profs:
        query += " AND PROFESSOR NOT IN %s"
        params += [tuple(excluded_profs)]
    cursor.execute(query, params)
    sessions = cursor.fetchall()
    conn.close()
    return sessions

if 'selected_courses' not in st.session_state:
    st.session_state.selected_courses = ["", "", "", ""]
if 'busy_slots' not in st.session_state:
    st.session_state.busy_slots = set()
if 'excluded_professors' not in st.session_state:
    st.session_state.excluded_professors = []
if 'schedule_results' not in st.session_state:
    st.session_state.schedule_results = []

with st.sidebar:
    st.header("Course Selection")
    for i in range(4):
        course_placeholder = st.empty()
        course_input = course_placeholder.text_input(f"Select Course {i+1}", st.session_state.selected_courses[i], key=f"course_{i}")
        if course_input:
            suggestions = get_course_suggestions(course_input)
            if suggestions:
                selected_course = st.selectbox(f"Suggestions for Course {i+1}", suggestions, key=f"suggestion_{i}")
                st.session_state.selected_courses[i] = selected_course
            else:
                st.session_state.selected_courses[i] = course_input
        else:
            st.session_state.selected_courses[i] = ""
    st.header("Exclude Professors")
    all_professors = get_all_professors()
    st.session_state.excluded_professors = st.multiselect("Select Professors to Exclude", all_professors)
    st.header("Busy Time Selection")
    select_busy_mode = st.checkbox("Select Busy Time on the Calendar")
    if st.button("Find the Schedules"):
        selected_courses = [course for course in st.session_state.selected_courses if course]
        excluded_professors = st.session_state.excluded_professors
        if not selected_courses:
            st.error("Please select at least one course.")
        else:
            sessions = get_sessions_for_courses(selected_courses, excluded_professors)
            if not sessions:
                st.error("No sessions found for the selected courses.")
            else:
                total_sets = len(selected_courses)
                course_to_sessions = {}
                for course in selected_courses:
                    course_to_sessions[course] = []
                for session in sessions:
                    session_id, course_name, session_name, time_array = session
                    time_bits = time_array
                    time_bits = [int(t) for t in time_bits]
                    course_to_sessions[course_name].append({
                        'id': session_id,
                        'time_bits': time_bits,
                        'session_name': session_name
                    })
                py_sets = []
                for course in selected_courses:
                    course_sessions = course_to_sessions[course]
                    session_list = []
                    for session in course_sessions:
                        session_data = session['time_bits'] + [session['id']]
                        session_list.append(session_data)
                    py_sets.append(session_list)
                times = [f"{hour}:{minute:02d}" for hour in range(8, 24) for minute in [0, 30]]
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
                leisure_time_bits = [0] * 6
                for slot in st.session_state.busy_slots:
                    row_idx, day = slot
                    day_index = days.index(day)
                    bit_position = row_idx
                    leisure_time_bits[day_index] |= 1 << bit_position
                result_list = autoschedulemodule.get_best_schedules(
                    total_sets,
                    py_sets,
                    leisure_time_bits
                )
                st.session_state.schedule_results = result_list

st.header("Weekly Calendar")
times = [f"{hour}:{minute:02d}" for hour in range(8, 24) for minute in [0, 30]]
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
data = {"Time": times}
for day in days:
    data[day] = [""] * len(times)
calendar_df = pd.DataFrame(data)
for idx, row in calendar_df.iterrows():
    for day in days:
        key = (idx, day)
        if key in st.session_state.busy_slots:
            calendar_df.at[idx, day] = "Busy"
gb = GridOptionsBuilder.from_dataframe(calendar_df)
gb.configure_selection(selection_mode='multiple', use_checkbox=False, suppressRowClickSelection=False)
grid_options = gb.build()
grid_response = AgGrid(
    calendar_df,
    gridOptions=grid_options,
    enable_enterprise_modules=False,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    fit_columns_on_grid_load=True,
    height=600,
    allow_unsafe_jscode=True,
    theme='streamlit',
    reload_data=True
)
if select_busy_mode:
    selected = grid_response['selected_cells']
    for cell in selected:
        key = (cell['rowIndex'], cell['colId'])
        if key in st.session_state.busy_slots:
            st.session_state.busy_slots.remove(key)
        else:
            st.session_state.busy_slots.add(key)
    for idx, row in calendar_df.iterrows():
        for day in days:
            key = (idx, day)
            if key in st.session_state.busy_slots:
                calendar_df.at[idx, day] = "Busy"
            else:
                calendar_df.at[idx, day] = ""
    grid_response = AgGrid(
        calendar_df,
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True,
        height=600,
        allow_unsafe_jscode=True,
        theme='streamlit',
        reload_data=True
    )
if st.session_state.schedule_results:
    st.header("Generated Schedules")
    schedule_colors = {}
    color_palette = ['#FF6633', '#FF33FF', '#00B3E6', '#E6B333',
                     '#3366E6', '#999966', '#99FF99', '#B34D4D',
                     '#80B300', '#809900', '#E6B3B3', '#6680B3',
                     '#66991A', '#FF99E6', '#CCFF1A', '#FF1A66',
                     '#E6331A', '#33FFCC', '#66994D', '#B366CC',
                     '#4D8000', '#B33300', '#CC80CC', '#66664D',
                     '#991AFF', '#E666FF', '#4DB3FF', '#1AB399',
                     '#E666B3', '#33991A', '#CC9999', '#B3B31A',
                     '#00E680', '#4D8066', '#809980', '#E6FF80',
                     '#1AFF33', '#999933', '#FF3380', '#CCCC00',
                     '#66E64D', '#4D80CC', '#9900B3', '#E64D66',
                     '#4DB380', '#FF4D4D', '#99E6E6', '#6666FF']
    schedule_colors = {}
    for idx, schedule in enumerate(st.session_state.schedule_results):
        st.subheader(f"Schedule {idx+1} (Penalty: {schedule['penalty']})")
        ids = schedule['ids']
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SESSION_ID, COURSE_NAME, SESSION_NAME, TIME
            FROM SESSIONS
            WHERE SESSION_ID IN %s
        """, (tuple(ids),))
        schedule_sessions = cursor.fetchall()
        conn.close()
        for session in schedule_sessions:
            session_id, course_name, session_name, time_array = session
            if course_name not in schedule_colors:
                schedule_colors[course_name] = random.choice(color_palette)
                color_palette.remove(schedule_colors[course_name])
        for session in schedule_sessions:
            session_id, course_name, session_name, time_array = session
            color = schedule_colors[course_name]
            st.markdown(f"<span style='color:{color}'>{course_name} - {session_name}</span>", unsafe_allow_html=True)
            time_bits = [int(t) for t in time_array]
            for day_index, day_bits in enumerate(time_bits):
                for bit_position in range(32):
                    if day_bits & (1 << bit_position):
                        row_idx = bit_position
                        day = days[day_index]
                        calendar_df.at[row_idx, day] = f"<div style='background-color:{color};width:100%;height:100%'></div>"
        grid_response = AgGrid(
            calendar_df,
            gridOptions=grid_options,
            enable_enterprise_modules=False,
            update_mode=GridUpdateMode.NO_UPDATE,
            fit_columns_on_grid_load=True,
            height=600,
            allow_unsafe_jscode=True,
            theme='streamlit',
            reload_data=True,
            unsafe_allow_html=True
        )
