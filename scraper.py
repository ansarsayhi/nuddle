from playwright.sync_api import sync_playwright
import time
import psycopg2  
from psycopg2 import sql







def set_up():
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    wpage = browser.new_page()
    wpage.goto('https://registrar.nu.edu.kz/course-catalog')
    wpage.wait_for_selector('#searchResultDiv')
    wpage.select_option('#semesterComboId', index=1)
    wpage.query_selector("#search-opt-div > div:nth-child(5) > div.optionTitle.inactive > span").click()
    wpage.select_option("#levelComboId", index=5)
    wpage.wait_for_selector('#limitComboIdBottom')
    wpage.select_option('#limitComboIdBottom', index=5)
    return p, browser, wpage

def tear_down(browser, p):
    if browser:
        browser.close()
    if p:
        p.stop()



def get_data(wpage):
    pages = wpage.query_selector_all('#pageComboIdBottom option')
    data = []

    def turn_pages(page):
        value = page.get_attribute('value')
        wpage.select_option("#pageComboIdBottom", value=value)
        wpage.wait_for_selector('#searchResultDiv')

    def get_course_name(search_result):
        return search_result.query_selector('table > tbody > tr:nth-child(1) > td:nth-child(1)').inner_text().strip()

    def get_course_credits(search_result):
        return search_result.query_selector('table > tbody > tr:nth-child(1) > td:nth-child(4)').inner_text().strip()

    def get_sessions(search_result, course_name):

        def get_session_type(session_name):
            for i in range(len(session_name)):
                if not session_name[i].isdigit():
                    return session_name[i:]

        def get_time(record):
            time_relevance = 1
            day_bits = [0] * 6  

            def get_slot(time_str):
                nonlocal time_relevance 
                time_part, period = time_str.strip().split()
                hour, minute = map(int, time_part.split(':'))
                if period == "PM" and hour != 12:
                    hour += 12
                if period == "AM" and hour == 12:
                    hour = 0
                if period == "PM" and hour == 23:
                    time_relevance = 0 
                slot_index = (hour - 8) * 2 + (1 if minute >= 30 else 0)
                return slot_index

            parts = record.strip().split()
            days_str = parts[0]
            time_range = ' '.join(parts[1:])
            start_time, end_time = time_range.split('-')
            start_slot = get_slot(start_time)
            end_slot = get_slot(end_time)

            days_map = {'M': 0, 'T': 1, 'W': 2, 'R': 3, 'F': 4, 'S': 5}
            for day_char in days_str:
                day_index = days_map[day_char]
                for slot in range(start_slot, end_slot + 1):
                    bit_position = slot  
                    day_bits[day_index] |= 1 << bit_position  

            return day_bits, time_relevance


        def get_availability(enrollment):
            numerator, denominator = enrollment.split('/')
            return 0 if (numerator == denominator) else 1

        search_result.query_selector(".scheduleButton").click()
        time.sleep(1)
        schedules = search_result.query_selector_all(
            '[id^="scheduleDiv"] > div > table > tbody > tr:not(:first-child)'
        )
        sessions = []
        for schedule in schedules:

            time_record = schedule.query_selector('td:nth-child(2)').inner_text()
            time_slots, time_relevance = get_time(time_record)
            session = {
                'SESSION_NAME': (session_name := schedule.query_selector('td:nth-child(1)').inner_text()),
                'SESSION_TYPE': get_session_type(session_name),
                'TIME_RECORD': time_record,
                'TIME_RELEVANCE': time_relevance,
                'TIME': time_slots,
                'ENROLLMENT': (enrollment := schedule.query_selector('td:nth-child(3)').inner_text()),
                'AVAILABILITY': get_availability(enrollment),
                'PROFESSOR': schedule.query_selector('td:nth-child(4)').inner_text(),
                'COURSE': course_name
            }
            sessions.append(session)
        return sessions

    try: 
        for page in pages:
            turn_pages(page)
            time.sleep(1)  
            search_results = wpage.query_selector_all('#searchResultDiv > div')
            for search_result in search_results:
                course_name = get_course_name(search_result)
                course_credits = get_course_credits(search_result)
                course_data = {
                    "COURSE_NAME": course_name,
                    "COURSE_CREDITS": course_credits,
                    "COURSE_SESSIONS": get_sessions(search_result, course_name)
                }
                data.append(course_data)
                print(course_data)
    finally:
        return data

def fill_db(data, db_params):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS COURSES (
        COURSE_NAME VARCHAR PRIMARY KEY,
        COURSE_CREDITS VARCHAR
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SESSIONS (
        SESSION_ID SERIAL PRIMARY KEY,
        COURSE_NAME VARCHAR REFERENCES COURSES(COURSE_NAME),
        SESSION_NAME VARCHAR,
        SESSION_TYPE VARCHAR,
        TIME_RECORD VARCHAR,
        TIME_RELEVANCE INTEGER,
        TIME BIGINT[],
        ENROLLMENT VARCHAR,
        AVAILABILITY INTEGER,
        PROFESSOR VARCHAR
    )
    ''')
    conn.commit()

    for course in data:

        course_name = course["COURSE_NAME"]
        course_credits = course["COURSE_CREDITS"]

        cursor.execute('''
        INSERT INTO COURSES (COURSE_NAME, COURSE_CREDITS)
        VALUES (%s, %s)
        ON CONFLICT (COURSE_NAME) DO UPDATE SET COURSE_CREDITS = EXCLUDED.COURSE_CREDITS
        ''', (course_name, course_credits))

        for session in course["COURSE_SESSIONS"]:

            session_name = session["SESSION_NAME"]
            session_type = session["SESSION_TYPE"]
            time_record = session["TIME_RECORD"]
            time_relevance = session['TIME_RELEVANCE']
            time_slots = session["TIME"]
            enrollment = session["ENROLLMENT"]
            availability = session["AVAILABILITY"]
            professor = session["PROFESSOR"]

            cursor.execute('''
            INSERT INTO SESSIONS (
                COURSE_NAME, SESSION_NAME, SESSION_TYPE, TIME_RECORD,
                TIME_RELEVANCE, TIME, ENROLLMENT, AVAILABILITY, PROFESSOR
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (course_name, session_name, session_type, time_record,
                  time_relevance, time_slots, enrollment, availability, professor))
    conn.commit()
    conn.close()

def main():
    p, browser, wpage = set_up()
    data = get_data(wpage)

    db_params = {
        'dbname': 'courses_n_sessions',
        'user': 'ansarantayev',
        'password': 'ansar111',
        'host': 'localhost',
        'port': 5432
    }

    fill_db(data, db_params)
    tear_down(browser, p)

if __name__ == "__main__":
    main()
