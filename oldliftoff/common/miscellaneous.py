def ask_user_yn(question: str) -> bool:
    while True:
        answer = str(input(f"\n{question:s} (y/n): ")).lower().strip()
        if answer == "y":
            return True
        if answer == "n":
            return False
