import json
import math
import time

import pandas as pd
import requests

from courses_config_local import current_term


# Function for gathering a list of old courses to be archived.
# The actual step of archiving the courses can be done in Alma via running the
# "Course Bulk Update" job.
def get_course_proc_dept_list(api_key, proc_dept):
    data = []
    courselistarray = []

    format = "format=json"
    headers = {
        "Authorization": f"apikey {api_key}",
        "Content-Type": "application/json"
    }

    countapicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?{format}&apikey={api_key}'
    countresponse = requests.get(countapicall.format(format=format, api_key=api_key))

    count = countresponse.json()['total_record_count']
    resumption = math.ceil(count / 100)

    for i in range(0, resumption):
        listapicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?{format}&apikey={api_key}&limit=100&offset={offset}'
        listresponse = requests.get(listapicall.format(format=format, api_key=api_key, offset=(i * 100)))
        master_course_dict = listresponse.json()

        for i in master_course_dict['course']:
            if 'processing_department' in i:
                if i['processing_department']['desc'] == 'Main Galvin Reserve':
                    courselistarray.append(i['id'])
                    course_data = {'Course ID': i['id'],
                                   'Course Name': i['name'],
                                   'Visibility': i['visibility'],
                                   'Created By': i['created_by'],
                                   'Creation Date': i['created_date'],
                                   'Archive Status': ''
                                   }
                    data.append(course_data)

    df = pd.DataFrame(data, columns=['Course ID', 'Course Name', 'Visibility', 'Created By', 'Creation Date'])

    csv_filename = 'archivedcourses.csv'
    df.to_csv(csv_filename, index=False)

    print(f"\nDataFrame saved to {csv_filename}")
    print('Total Courses to Archive: ' + str(len(data)))


# Function for cleaning up the original citations CSV from the bookstore.
def citations_cleanup(d, citations_filepath, dmmsid, api_key):
    mmsid_dict = {}

    # If a title is associated with multiple ISBNs, Alma saves them all in one cell. The following loop
    # will split all ISBNs apart and associate the MMSID with them as key-value pairs in a MMSID dictionary.
    for index, row in dmmsid.iterrows():
        raw_isbns = row['ISBN']
        mmsid = row["MMS Id"]
        isbns = raw_isbns.split("; ")
        for i in isbns:
            mmsid_dict[i] = mmsid

    for index, row in d.iterrows():
        # Format the list of citations properly so the Course Updater can understand it
        # Start by creating a column for the current semester
        current_semester = current_term[0] + str(current_term[1])
        d.loc[index, 'Semester'] = current_semester

        # Construct a searchable course code for each citation
        raw_course_code = row['Section']
        course_code = raw_course_code.replace(' ', '') + current_semester

        # Create a column for the new course codes
        d.loc[index, 'course_code'] = course_code

        # Indicate the column in the citations list containing ISBNs
        isbn = row["ISBN"]

        # Match ISBN numbers to the MMSID list retrieved from Alma Analytics
        # Create a column for MMSIDs
        if isbn in mmsid_dict:
            mmsid = mmsid_dict[isbn]
            print(row['Title'] + ": MMSID Found")
            print(mmsid)
            d.loc[index, 'MMSID'] = mmsid
            d.to_csv(citations_filepath)

            # Make an API call on the ISBN to determine the held item's location
            apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/{mmsid}/holdings/ALL/items?{format}&apikey={api_key}'
            format = "format=json"
            call_elements = {"mmsid": mmsid,
                             "format": format,
                             "api_key": api_key}

            response = requests.get(apicall.format(**call_elements))

            bib_dict = response.json()

            locations = []
            callnums = []
            barcodes = []

            if bib_dict["total_record_count"] == 0:
                locations.append("No Physical Holdings")

            else:
                for i in bib_dict["item"]:

                    locations.append(i["item_data"]["location"]["desc"])
                    barcodes.append(i['item_data']['barcode'])
                    callnums.append(i["holding_data"]["permanent_call_number"])

                    if i["bib_data"]["isbn"] == isbn:
                        d.loc[index, 'Holdings'] = "ISBN Match"

                    else:
                        d.loc[index, 'Holdings'] = "Different ISBN Held"

            d.loc[index, 'Location'] = ', '.join(locations)
            d.loc[index, 'Barcode'] = ', '.join(barcodes)
            d.loc[index, 'Call Number'] = ', '.join(callnums)

    d.to_csv(citations_filepath, index=False)


# Collect course data from the CSV file
def GetCourseData(api_key, current_term, row, codes_dict):
    course_code = row['Section']
    course_name = row['Course Title']
    course_dept_raw, course_number, course_section_number = course_code.split(" ")
    course_section = str(course_section_number) + " " + str(current_term[0]) + str(current_term[1])
    course_dept = codes_dict[row['Department']]
    course_term = current_term[0]

    course_start_date = current_term[2]
    course_end_date = current_term[3]
    course_year = current_term[1]

    #The course CSV file contains only faculty names, but Alma needs primary identifiers.
    #The following lines of code will make an API call to retrieve the primary ID of the instructor.
    raw_name = row["Instructor"]

    try:
        instructors = raw_name.split(",")
        prim_inst = instructors[0]
        instructor = prim_inst.replace(' ', '%2b')

        #Make an API call to search for the instructor name and retrieve a Primary ID.
        apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/users?{format}&apikey={api_key}&q=ALL~{instructor}'
        format = "format=json"
        call_elements = {"format": format,
                         "api_key": api_key,
                         "instructor": instructor}

        response = requests.get(apicall.format(**call_elements))

        instr_response = response.json()
        course_instructor_id = ""

        if instr_response["total_record_count"] > 1:
            for i in instr_response["user"]:
                primary_id = i["primary_id"]
                inst_apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/users/{primary_id}?{format}&apikey={api_key}'
                inst_call_elements = {"format": format,
                                      "api_key": api_key,
                                      "primary_id": primary_id}
                is_empl_response = requests.get(inst_apicall.format(**inst_call_elements))
                user_group = is_empl_response.json()["user_group"]["desc"]

                if user_group == "Academic Employees":
                    course_instructor_id = primary_id

        else:
            course_instructor_id = instr_response["user"][0]["primary_id"]

    except:
        course_instructor_id = ""

    semester = str(course_term + course_year)
    searchable_id = str(course_code.replace(" ", "") + str(semester))

    course_data = [course_code,
                   course_name,
                   course_section,
                   course_dept,
                   course_term,
                   course_start_date,
                   course_end_date,
                   course_year,
                   course_instructor_id,
                   searchable_id]

    # Construct a dictionary to contain all the course data so it can be dumped to a JSON file
    course_dict = {
        'code': course_code,
        'name': course_name,
        'section': course_section,
        'academic_department': {'value' : course_dept},
        'processing_department': {'value' : "Main",
                                   'desc' : 'Main Galvin Reserve'},
        'term': [{'value' : course_term}],
        'status': "ACTIVE",
        'start_date': str(course_start_date + 'Z'),
        'end_date': str(course_end_date + 'Z'),
        'year': course_year,
        'instructor': [{'primary_id': course_instructor_id}],
        'searchable_id': [searchable_id, course_number]
    }
    print(course_dict['code'] + " course data compiled.")
    return course_dict


def CreateCourse(course_dict, api_key):

    apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?{format}&apikey={api_key}'
    format = "format=json"
    headers = {
        "Authorization": f"apikey {api_key}",
        "Content-Type": "application/json"
    }
    response = requests.get(apicall.format(format=format, api_key=api_key))


    if response.status_code == 200:

        # API call successful
        add_course = requests.post(apicall.format(format=format, api_key=api_key), headers=headers,
                                   data=json.dumps(course_dict))

        if add_course.status_code == 200:
            print(str(course_dict['code']) + " Successfully Added")
            add_course_json = add_course.json()
            course_id = add_course_json['id']
            time.sleep(2)
            new_apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}?{format}&apikey={api_key}'
            response2 = requests.get(new_apicall.format( course_id=course_id, format=format, api_key=api_key))
            new_course_data = response2.json()
            return course_id

        else:
            #Add course failed; the course may already exist. Try updating the existing course information.
            try:
                search_id = course_dict['searchable_id'][0]
                get_id_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/?{format}&apikey={api_key}&q=searchable_ids~{search_id}'
                course_update_get = requests.get(get_id_call.format(format=format, api_key=api_key, search_id=search_id))
                course_id = course_update_get.json()['course'][0]['id']
                update_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}?{format}&apikey={api_key}'
                update_course = requests.put(update_call.format(course_id=course_id, format=format, api_key=api_key), headers=headers,
                                           data=json.dumps(course_dict))
                course_id = update_course.json()['id']
                print(str(course_dict['code']) + " Already Existed; Successfully Updated")
                return course_id

            #if that doesn't work, move on to the next course.
            except:
                course_add_error = "COURSE NOT ADDED/UPDATED"
                print(course_add_error)
                return course_add_error
    else:
        #API console is down
        api_down = "Alma API is down"
        print(api_down)
        quit()


def CreateReadingList(course_id, api_key):

    apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}?{format}&apikey={api_key}'
    format = "format=json"
    headers = {
        "Authorization": f"apikey {api_key}",
        "Content-Type": "application/json"
    }
    response = requests.get(apicall.format(course_id=course_id, format=format, api_key=api_key))

    if response.status_code == 200:
        course_data = response.json()

        # Set up data dictionary for the new reading list
        try:
            list_code_draft = str(
                course_data['code'] + "-" + str(course_data['section']) + "-" + course_data['instructor'][0][
                    'last_name'])
            list_code = list_code_draft.replace(" ", "-")

        except:
            list_code_draft = str(course_data['code'] + "-" + str(course_data['section']) + "-" + "UnknownInstructor")
            list_code = list_code_draft.replace(" ", "-")

        reading_list_dict = {
            'code': list_code,
            'name': str(course_data['name']),
            'due_back_date': str(course_data['end_date']),
            'status': {'value': 'Complete'},
            'visibility': {'value': 'OPEN_TO_WORLD'},
            'publishingStatus': {'value': 'DRAFT'}
        }

        #Check to see if a reading list already exists for this course

        reading_list_check_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists?{format}&apikey={api_key}'
        check_reading_list = requests.get(reading_list_check_call.format(course_id=course_id, format=format, api_key=api_key))
        chk_read_list_dict = check_reading_list.json()

        #If no reading list exists for the course, create one by pushing the data dictionary to Alma
        if 'reading_list' not in chk_read_list_dict:

            # Push data dictionary to Alma as a JSON
            list_apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists?{format}&apikey={api_key}'
            list_post = requests.post(list_apicall.format(course_id=course_id, format=format, api_key=api_key), data=json.dumps(reading_list_dict),headers=headers)
            time.sleep(2)

            if list_post.status_code == 200:
                check_list_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists?{format}&apikey={api_key}&q=code~{list_code}'
                check_list = requests.get(check_list_call.format(course_id=course_id, format=format, api_key=api_key, list_code=list_code))
                new_list_data = check_list.json()
                confirmed_list_code = new_list_data['reading_list'][0]['code']
                course_data['reading_lists'] = new_list_data

                associate_list = requests.put(apicall.format(course_id=course_id,format = format, api_key=api_key), headers=headers, data=json.dumps(course_data))

                if associate_list.status_code == 200:
                    print(str("Reading List " + confirmed_list_code + " Created"))
                    return confirmed_list_code

                else:
                    print(str(confirmed_list_code + " created, but course association Failed"))
                    pass

        else:

            get_existing_list_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists?{format}&apikey={api_key}'
            get_existing_list = requests.get(get_existing_list_call.format(course_id=course_id, format=format,api_key=api_key))
            existing_list_data = get_existing_list.json()
            existing_list_id = existing_list_data['reading_list'][0]['id']

            existing_list_apicall = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists/{existing_list_id}?{format}&apikey={api_key}'
            update_list = requests.get(existing_list_apicall.format(course_id=course_id, existing_list_id=existing_list_id, format=format, api_key=api_key))
            print("Existing list updated: " + str(update_list.json()['code']))
            current_list_code = update_list.json()['code']
            return current_list_code

    else:
        # Check API Call Failed
        list_error = 'No Course Found - List Not Created'
        print(list_error)
        pass

    print("\n")


# This function should be run after all courses and reading lists have either been
# created or updated. Use a "For" loop to iterate over a CSV of citations and associate
# each one with the appropriate course and reading list.
def AddCitation(row, api_key):

    format = "format=json"
    headers = {
        "Authorization": f"apikey {api_key}",
        "Content-Type": "application/json"
    }

    mms_id = str(row['MMSID'])
    search_id = row['course_code']

    # Pandas assigns blank cells the value of "nan" or "not a number". The conditional below
    # allows the addition of the citation to move forward only if a MMS ID is present for the
    # give course.
    if mms_id != "nan":
        # Construct a dictionary for the citation that can be pushed to Alma as JSON
        citation_dict = {
            'status' : {'value': 'Complete'},
            "copyrights_status": {
                "value": "NOTDETERMINED"
            },
            'metadata' : {
                'mms_id' : mms_id
            },
            'type' : {
                'value' : 'BK',
                'desc' : 'Physical Book'
            }
            }

        course_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?{format}&apikey={api_key}&q=searchable_ids~{search_id}'
        get_course_data = requests.get(course_call.format(format=format, api_key=api_key, search_id=search_id))
        course_data = get_course_data.json()
        try:
            course_id = str(course_data['course'][0]['id'])

        except:
            return(str(search_id) + " Course Not Found for Citation")


        course_lists_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists?{format}&apikey={api_key}'
        get_list_id = requests.get(course_lists_call.format(course_id=course_id, format=format, api_key=api_key))
        list_data = get_list_id.json()
        list_id = str(list_data['reading_list'][0]['id'])


        #Check if the citation already exists in this reading list

        check_cit_call = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists/{list_id}/citations?{format}&apikey={api_key}"
        check_citation = requests.get(check_cit_call.format(course_id=course_id, list_id=list_id, format=format, api_key=api_key))
        citations_data = check_citation.json()
        citations_list = []

        if "citation" in citations_data:
            for i in citations_data["citation"]:
                citation_mms_id = i["metadata"]["mms_id"]
                citations_list.append(citation_mms_id)

        if mms_id not in citations_list:
            list_call = 'https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses/{course_id}/reading-lists/{list_id}/citations?{format}&apikey={api_key}'
            post_citation = requests.post(list_call.format(course_id=course_id, list_id=list_id, format=format, api_key=api_key), headers=headers, data=json.dumps(citation_dict))

            if post_citation.status_code == 200:
                return str(search_id + ": citation successfully posted")

            else:
                return str(search_id + ": citation not posted")

        else:
            return str(search_id + ": Citation Already Exists; Reading List Not Updated")
    else:
        return str(search_id + ": No Citation For This Course")


