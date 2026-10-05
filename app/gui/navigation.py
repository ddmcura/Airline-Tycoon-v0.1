"""Small section map and one active page host; no gameplay ownership."""
SECTIONS = {
    'Dashboard': (('Dashboard','Overview'),),
    'Operations': (('Flights','Flights'),('Bookings','Bookings'),('Scheduling','Schedule')),
    'Network': (('Research','Research'),),
    'Fleet': (('Fleet Overview','Fleet'),('Acquire Aircraft','Acquire')),
    'Finance': (('Finance','Finance'),),
    'Game / System': (('Save / Bookmarks','Saves'),),
}


def section_for(page):
    if page == 'Aircraft Details': return 'Fleet'
    return next(section for section, pages in SECTIONS.items() if any(value==page for _,value in pages))
