import questionary
try:
    ans = questionary.select("Select one:", choices=[str(i) for i in range(20)]).ask()
    print("Ans:", ans)
except Exception as e:
    print("Error:", e)
