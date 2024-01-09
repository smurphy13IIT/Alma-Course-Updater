import pandas as pd

from AlmaCourseFunctions import citations_cleanup, get_course_proc_dept_list, GetCourseData, CreateCourse, \
    CreateReadingList, AddCitation
from courses_config import current_term, citations_filepath, mmsid_filepath, proc_dept, api_key
from dictionaries import codes_dict

# Open csv files listing course information, compiled from BN College Bookstore CSV files.
d = pd.read_csv(citations_filepath, dtype=str)
d['TempIndex'] = range(len(d))
d.set_index('TempIndex', inplace=True, drop=True)

columns_list = ["MMSID",
                "Location",
                "Holdings",
                "Barcode",
                "Call Number",
                "Semester",
                "course_code",
                "course_id",
                "list_code",
                "Status"]

for i in columns_list:
    if i not in d.columns:
        d[i] = None


dmmsid = pd.read_csv(mmsid_filepath, dtype=str)
dmmsid['TempIndex'] = range(len(dmmsid))
dmmsid.set_index("TempIndex", inplace=True, drop=True)

while True:
    select_action = input('''What step of the Course Reserves process would you like to perform?
    For gathering a list of courses to archive:                         Type "archive"
    For cleaning up the initial citation list :                         Type "cleanup"
    For creating courses and reading lists from bookstore course data:  Type "courses"
    For adding citations to reading lists:                              Type "citations"
    To exit this script:                                                Type "quit"\n
    Enter Your Selection: ''')

    if select_action == 'cleanup':
        cleanup = citations_cleanup(d, citations_filepath, dmmsid, api_key)
        print("\nCitation list cleanup complete.\n")

    elif select_action == 'archive':
        get_course_proc_dept_list(api_key, proc_dept)
        print("\nOld courses compiled to archivedcourses.csv. Ready for archiving.\n")

    elif select_action == 'courses':
        for index, row in d.iterrows():
            course_dict = GetCourseData(api_key, current_term, row, codes_dict)
            print(course_dict)

            if row['School'] != "College of Architecture":
                course_dict = GetCourseData(api_key, current_term, row, codes_dict)

                # Push course data to Alma
                course_id = CreateCourse(course_dict, api_key)

                # Update the CSV with the new Course ID
                d.loc[index, 'course_id'] = course_id

                # Update the CSV with the new Reading List Code
                reading_list_id = CreateReadingList(course_id, api_key)
                d.loc[index, 'list_code'] = reading_list_id

            d.to_csv(citations_filepath, index=False)

        print("\nCourses and reading lists have been created.\n")

    elif select_action == 'citations':
        for index, row in d.iterrows():
            add_citation = AddCitation(row, api_key)
            d.loc[index, 'Status'] = add_citation
            print(add_citation)

            d.to_csv(citations_filepath, index=False)

        print('''\nCitations added to courses.\n
        Course Reserves update process is complete.\n''')

    elif select_action == 'quit':
        break

    else:
        print('''\nInvalid entry. Please select one of these options:
        For gathering a list of courses to archive:                         Type "archive"
        For cleaning up the initial citation list :                         Type "cleanup"
        For creating courses and reading lists from bookstore course data:  Type "courses"
        For adding citations to reading lists:                              Type "citations"
        To exit this script:                                                Type "quit"\n
        Enter Your Selection: ''')