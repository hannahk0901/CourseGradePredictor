import RateMyProfessor_Database_APIs

if __name__ == '__main__':
    try:
        school_id = '1381'

        all_professors = RateMyProfessor_Database_APIs.fetch_all_professors_from_a_school(school_id)
        print(f"Fetched {len(all_professors)} professors")
        print("------------------- All Professor in a school information (First 10 showed) -------------------")
        for prof in all_professors[:10]:
            print(prof)
            print("\n")

        professor = RateMyProfessor_Database_APIs.fetch_a_professor(200147)
        print("------------------- Professor Information -------------------")
        print(professor)

        school = RateMyProfessor_Database_APIs.fetch_a_school(school_id)
        print("------------------- School Information -------------------")
        print(school)
        
    except Exception as e:
        print(f"An error occurred: {e}")
