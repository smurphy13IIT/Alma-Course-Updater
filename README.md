# Alma-Course-Updater

**Overview**

This collection of files can be used to update Course Reserves information in Alma given a list of citations from the BN College inventory system.

The course reserves update process happens in four phases:

1) _Archive:_ A list of existing courses associated with a given processing department in Alma is collected. This can be uploaded to Alma so the Course Bulk Update job can mark them as archived.
2) _Citations Cleanup:_ After a CSV list of citations is obtained from BN College, a report is generated in Alma Analytics taking ISBNs as its input and exporting a list of corresponding MMS IDs to indicate which items are currently owned by the library. If an item is owned, the Alma API is queried to retrieve additional information (location and call number), and this information is added back into the citations CSV file.
3) _Course and Reading List Creation:_ Each course listed in the BN College CSV file is given an entry in Alma, along with an empty reading list, via Alma API.
4) _Adding Citations:_ Each citation that has an identified MMS ID from step 2 is associated with its corresponding reading list from step 3.

Each step of the process can be initiated separately by running the Alma-Course-Updater.py script and supplying the respective user input. The function that handles each step includes code that double-checks for the presence of a given course, reading list, or citation before moving forward with updating that particular element in Alma, so the functions can be run each time a course change occurs or a new textbook is purchased for a given course.

**Complete These Steps Before Running This Script**

1) Download this repository to your local directory.
2) Update the courses_config.py file with your local variables.
3) Update the dictionaries.py file with your institutions academic department data.
4) Retrieve a list of citations from your institution's BN College vendor interface. Put it in the repository directory and rename it citations.csv.
5) Build an Alma Analytics report with two datafields - ISBN and MMS ID - and create a filter so you can supply all the ISBNs from the citations list and receive a list of corresponding MMS IDs. Name the resulting CSV file mmsid.csv and save in the repository directory.
6) Run Alma-Course-Updater.py. If you want to archive all existing courses in Alma, start by typing _archive._ You'll get a list of course IDs for the processing department you provided in the course_config.py file. You can use the Alma Course Bulk Update job to change the visibility of these courses to "archived".
7) Run Alma-Course-Updater.py and type _cleanup_ to initiate the process of updating the citations.csv file with the MMS IDs of citations your library already owns. You can use this as a shelflist to retrieve items from other locations that need to be moved to the Reserves shelves, too.
8) Run Alma-Course-Updater.py and type _courses_ to create course and reading list objects in Alma using data from the citations.csv file.
9) Run Alma-Course-Updater.py and type _citations_ to add owned textbook citations to corresponding course reading lists. They will be visible to users in Primo after the start date that is provided in the current_term variable within the courses_config.py file.
10) Run steps 7 and 9 (in that order) each time a new textbook or set of textbooks is catalogued for reserves in Alma.

**The course update process is complete!**
