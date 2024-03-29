import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import numpy as np
from model_lstm import *
from plotting import *
from FVM_LossFunctions import lossFVMDiscretizedEqns

"""
python main.py 

dt = 0.01 SECONDS

"""
import time

# Début du chronomètre
start_time = time.time()

device = 'cuda' if torch.cuda.is_available() else 'cpu'  # device

# Définition de la géométrie 0<= x <=1 et 0<= y <=1 
Lx = 1
Ly = 1
# Coefficient de diffuvisité
nu = 0.01
# Pas spatial en x et en y
dx = 0.01
dy = 0.01
# Temps simulé et pas de temps dt
time = 0.52
dt = 1e-3
tsteps = int(time/dt + 1)
# Nombre de faces en X et en Y
Nx = int(Lx/dx)
Ny = int(Ly/dy)
# Surface en x et en y
dS = dx*dy
# Surfaces des directions Est (e), Ouest (w), Nord (n), Sud (s)
Ae = dy
Aw = dy
An = dx
As = dx
# Coefficients des flux diffusifs
De = nu*Ae
Dw = nu*Aw
Dn = nu*An
Ds = nu*As
# Vitesse dans les différentes directions, E, W, N, et S
ue, uw = 1, 1
vn, vs = 1, 1
# Coefficients des flux convectifs
Fe = ue*Ae
Fw = uw*Aw
Fn = vn*An
Fs = vs*As
# Supposons que data soit un tableau numpy de forme (N, 4) où N est le nombre d'échantillons
# et chaque ligne est un quadruplet (t, x, y, u)
#file_path = "solution_u_implicit_data.csv"
file_path = "simulation_data_final.csv"
CODE_TEST = "05FevH24Test_01"

data = pd.read_csv(file_path)

def truncate_two_decimals(value):
    return int(value * 100) / 100.0

def truncate_three_decimals(value):
    return int(value * 1000) / 1000.0

# Fonction pour vérifier si un nombre est un multiple de 10^-2
def is_multiple_of_10_minus_2(value, tolerance=1e-4):
    return abs(value * 100 - round(value * 100)) < tolerance

#print(data['temps'].unique())

#data["temps"] = data["temps"].apply(truncate_three_decimals)
# Filtrer les données pour ne garder que celles dont le temps est un multiple de 10^-2
data = data[data["temps"].apply(is_multiple_of_10_minus_2)]
#print(data['temps'].unique())

#data["x"] = data["x"].apply(truncate_two_decimals)
#data["y"] = data["y"].apply(truncate_two_decimals)
#data["temps"] = data["temps"].apply(truncate_three_decimals)
#data["u"] = data["u"].apply(truncate_three_decimals)

# Séparation des entrées et des cibles en utilisant .iloc
inputs = data.iloc[:, :-1].values  # Prend tout sauf la dernière colonne
targets = data.iloc[:, -1].values  # Prend seulement la dernière colonne

n = len(inputs)
idx_train = int(n * 0.4)
#idx_val = idx_train + int(n * 0.2)

# Fonction pour créer des séquences
def create_sequences(data, targets, sequence_length):
    X, Y = [], []
    for i in range(len(data) - sequence_length):
        X.append(data[i:i+sequence_length])
        Y.append(targets[i+sequence_length])
    return np.array(X), np.array(Y)

def create_sequences_with_full_intervals(data, targets, sequence_length, interval_length=1681):
    X, Y = [], []
    for i in range(0, len(data) - sequence_length, interval_length):
        for j in range(i, i + interval_length - sequence_length):
            X.append(data[j:j+sequence_length])
            Y.append(targets[j+sequence_length])
    return np.array(X), np.array(Y)


# Création de séquences
sequence_length = 10
X, Y = create_sequences(inputs, targets, sequence_length)
X_train = X[:idx_train]
Y_train = Y[:idx_train]
X_test = X[idx_train:]
Y_test = Y[idx_train:]

X_train, X_val, Y_train, Y_val = train_test_split(X_train, Y_train, test_size=0.4, random_state=42)

X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
Y_train_tensor = torch.tensor(Y_train, dtype=torch.float32)
#print("X train shape", X_train_tensor.shape)
#print("Y train shape", Y_train_tensor.shape)

X_val_tensor = torch.tensor(X_val, dtype=torch.float32)
Y_val_tensor = torch.tensor(Y_val, dtype=torch.float32)

X_test_tensor = torch.tensor(X_test, dtype=torch.float32)
Y_test_tensor = torch.tensor(Y_test, dtype=torch.float32)

# Déplacer les tensors vers le GPU si disponible
if torch.cuda.is_available():
    X_train_tensor = X_train_tensor.cuda()
    Y_train_tensor = Y_train_tensor.cuda()
    X_val_tensor = X_val_tensor.cuda()
    Y_val_tensor = Y_val_tensor.cuda()
    X_test_tensor = X_test_tensor.cuda()
    Y_test_tensor = Y_test_tensor.cuda()

# Hyperparamètres
learning_rate = 1e-4
epochs = 200
input_dim = 3  # (t, x, y)
hidden_dim = 96
layer_dim = 1 
output_dim = 1

# Initialisation du modèle, de la fonction de coût et de l'optimiseur
model = LSTMModel(input_dim, hidden_dim, layer_dim, output_dim)

# TRANSFERED LEARNING
#model.load_state_dict(torch.load('model_path_TC_01.pth'))
#model.eval()  # Mettez le modèle en mode évaluation

if torch.cuda.is_available():
    model = model.cuda()
    
criterion = torch.nn.MSELoss()  # Erreur quadratique moyenne pour la régression
optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)


epoch = 0

val_outputs = model(X_val_tensor).squeeze(1)
val_loss = criterion(val_outputs, Y_val_tensor)

train_losses = []
val_losses = []
epochs_dat = []

"""
# Boucle d'entraînement
while (epoch <= epochs and val_loss.item() > 4.5e-8):
    model.train()
    optimizer.zero_grad()

    # Forward pass
    outputs = model(X_train_tensor).squeeze(1)
    loss = criterion(outputs, Y_train_tensor)

    # Backward pass et optimisation
    loss.backward()
    optimizer.step()

    # Évaluation sur l'ensemble de validation
    model.eval()
    val_outputs = model(X_val_tensor).squeeze(1)
    val_loss = criterion(val_outputs, Y_val_tensor)
    
    train_losses.append(loss.item())
    val_losses.append(val_loss.item())
    epochs_dat.append(epoch)
    
    if epoch % 5 == 0:
        print(f"Epoch {epoch}/{epochs}, Training Loss: {loss.item()}, Validation Loss: {val_loss.item()}")
        
    #if epoch % 10000 == 0:
        #torch.save(u_net.state_dict(), f'u_net_epoch_{epoch}.pth')
        #torch.save(model.state_dict(), f'u_lstmTC_06_net_epoch_{epoch}.pth')
        
    epoch += 1

"""
# Initialisation de la prédiction précédente, Tp
# Au départ, vous pouvez initialiser Tp avec des zéros ou avec la première valeur cible.
#Tp = torch.zeros_like(Y_train_tensor)
#if torch.cuda.is_available():
    #Tp = Tp.cuda()

# Boucle d'entraînement avec perte FVM prenant en compte T et Tp
while (epoch <= epochs and val_loss.item() > 4.5e-8):
    model.train()
    optimizer.zero_grad()

    # Forward pass pour obtenir la prédiction actuelle
    T = model(X_train_tensor).squeeze(1)
    #print("T shape", T.shape)
    # Initialisation de la perte totale
    # Initialisation de la perte totale
    total_fvm_loss = 0

    # Le nombre de points par pas de temps est 10000
    points_per_timestep = 10000

    # Calculer le nombre de pas de temps complets dans le tenseur T
    num_timesteps = T.shape[0] // points_per_timestep

    for i in range(num_timesteps-1):
        # Extraire les données pour le pas de temps actuel
        # Extraire Tp_timestep (pas de temps actuel)
        Tp_timestep = T[i * points_per_timestep:(i + 1) * points_per_timestep]
        # Extraire T_timestep (pas de temps futur)
        T_timestep = T[(i + 1) * points_per_timestep:(i + 2) * points_per_timestep]
        # Redimensionner pour chaque pas de temps
        T_timestep_reshaped = T_timestep.view(Ny, Nx)
        Tp_timestep_reshaped = Tp_timestep.view(Ny, Nx)

        # Calculer la perte pour ce pas de temps
        fvm_loss = lossFVMDiscretizedEqns(T_timestep_reshaped, Tp_timestep_reshaped, Nx, Ny, dx, dy, dS, dt, De, Dw, Dn, Ds, Fe, Fw, Fn, Fs)
        total_fvm_loss += fvm_loss

    # Calculer la perte moyenne sur tous les pas de temps
    mean_fvm_loss = total_fvm_loss / num_timesteps

    # Backward pass et optimisation
    mean_fvm_loss.backward()
    optimizer.step()

    # Mise à jour de Tp avec les valeurs actuelles de T pour le prochain pas de temps
    Tp = T.detach()  # Assurez-vous de détacher Tp pour éviter de construire un graphique de calcul

    # Évaluation sur l'ensemble de validation (peut nécessiter des ajustements similaires pour utiliser Tp)
    model.eval()
    T_val = model(X_val_tensor).squeeze(1)
    val_loss = criterion(T_val, Y_val_tensor)  # Ou utilisez la perte FVM si approprié

    # Enregistrement et affichage des pertes
    train_losses.append(fvm_loss.item())
    val_losses.append(val_loss.item())
    epochs_dat.append(epoch)
    
    if epoch % 10 == 0:
        print(f"Epoch {epoch}/{epochs}, Training FVM Loss: {fvm_loss.item()}, Validation Loss: {val_loss.item()}")
    
    epoch += 1



torch.save(model.state_dict(), f'model_final_{CODE_TEST}.pth')


# Supposons que 'data' est votre DataFrame et que 'temps' est la colonne contenant les temps
unique_times = data['temps'].unique()

# Supposons que 'data' est votre DataFrame
T_test = data[data['temps'].isin(unique_times)]['temps'].to_numpy()

max_errors = []

print("Results plotting")

for t in unique_times:
    if t >= 0.22 and t <= 0.5:  # Affichez les prédictions seulement après 0,2 secondes
        indices = np.where(X_test[:, -1, 0] == t)  # Utilisez le dernier pas de temps de chaque séquence
        #indices = np.where(X_test_2[:, 0] == t) 
        X_t = X_test[indices]
        Y_t = Y_test[indices]
        
        ind = np.where(data['temps'] == t)  # Utilisez le dernier pas de temps de chaque séquence
        #indices = np.where(X_test_2[:, 0] == t) 
        X_dat = data["x"].values[ind]
        Y_dat = data["y"].values[ind]
        U_dat = data["u"].values[ind]

        # Convertissez les données en tensors et déplacez-les sur le GPU si nécessaire
        X_tensor = torch.tensor(X_t, dtype=torch.float32)
        if torch.cuda.is_available():
            X_tensor = X_tensor.cuda()

        # Obtenez les prédictions du modèle
        with torch.no_grad():
            predicted_u = model(X_tensor).cpu().numpy().squeeze()

        # Calcul de l'erreur absolue
        error = np.abs(U_dat - predicted_u)
        max_errors.append(np.max(error))
        

        # Affichez les prédictions à l'aide des fonctions fournies
        #plot_side_by_side(X_t[:, -1, 1], X_t[:, -1, 2], Y_t, predicted_u, error, t)
        plot_side_by_side(X_dat, Y_dat, U_dat, predicted_u, error, t)
        #plot_side_by_side(X_t[:, 1], X_t[:, 2], Y_t, predicted_u, error, t)
        


average_max_error = np.mean(max_errors)
FINAL_max_error = np.max(max_errors)
print(f"Moyenne des erreurs maximales sur les pas de temps: {average_max_error}")
print(f"MAXIMUM des erreurs maximales sur les pas de temps: {FINAL_max_error}")

# 3. Afficher les pertes après l'entraînement
plt.figure(figsize=(10, 6))
plt.plot(train_losses, label='Training Loss')
plt.plot(val_losses, label='Validation Loss')
plt.xlabel('Epochs')
plt.ylabel('Loss')
plt.title('Training and Validation Losses over Epochs')
plt.legend()
plt.grid(False)

# Mettre l'échelle en log sur l'axe des ordonnées
plt.yscale('log')

# 4. Enregistrer le graphique
plt.savefig(f'losses_plot_{CODE_TEST}.png')
plt.show()

end_time = time.time()

execution_time = end_time - start_time

# Convertir en heures, minutes, secondes
hours = int(execution_time // 3600)
minutes = int((execution_time % 3600) // 60)
seconds = execution_time % 60

# Écrire dans un fichier
with open(f"temps_execution_{CODE_TEST}.txt", "w") as file:
    file.write(f"Temps d'exécution: {hours} heure(s), {minutes} minute(s) et {seconds:.2f} seconde(s)\n")
    file.write(f"Moyenne des erreurs maximales sur les pas de temps: {average_max_error}, \n MAXIMUM des erreurs maximales sur les pas de temps: {FINAL_max_error} \n")
