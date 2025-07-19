from models import PanelMaster, FileMeta
from database import SessionLocal

def insert_sample_data():
    db = SessionLocal()
    try:
        # Create sample panels
        panel1 = PanelMaster(panel_name="HR Documents", description="HR related files")
        panel2 = PanelMaster(panel_name="Finance Reports", description="Quarterly finance reports")
        db.add_all([panel1, panel2])
        db.commit()

        # Refresh to get panel IDs
        db.refresh(panel1)
        db.refresh(panel2)

        # Create sample files for each panel
        file1 = FileMeta(panel_id=panel1.panel_id, file_name="Employee_Handbook.pdf")
        file2 = FileMeta(panel_id=panel1.panel_id, file_name="Leave_Policy.docx")
        file3 = FileMeta(panel_id=panel2.panel_id, file_name="Q1_Report.xlsx")
        file4 = FileMeta(panel_id=panel2.panel_id, file_name="Q2_Report.xlsx")
        db.add_all([file1, file2, file3, file4])
        db.commit()

        print("Sample data inserted successfully.")
    finally:
        db.close()

if __name__ == "__main__":
    insert_sample_data()
    