from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)


# Upgrades
# - Password par mail
# - Ajouter les formules du trade

# BugFix
# - Erreur valeur de coin quand on achète et vend en même temps

### A livrer pour Fêta

## Upgrades
# - Add a maximum number of characters for username (7) else >= ...
# - Remplacer tous les messages d'erreur par des pop-ups dans les pages HTML
# - Filtre gloabl sur tous les coins

## BugFix
# Corriger la valeur des Coins dans le Leaderboard qui ne s'actualise pas
# - Ca bug dans le login quand ça marche pas
