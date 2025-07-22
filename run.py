from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)


# Upgrades
# - Add a maximum number of characters for username (7) else >= ...
# - Password par mail
# - Max printed limite characters in leaderboard = 7
# - Remplacer tous les messages d'erreur par des pop-ups dans les pages HTML

# BugFix
# - Erreur de valeur d'equity quand les actions montent et descendent
# - Erreur valeur de coin quand on achète et vend en même temps
# - Profit non correct
