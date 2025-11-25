# Używamy lekkiego obrazu Node.js
FROM node:20-alpine

WORKDIR /app

# Kopiujemy pliki konfiguracyjne pakietów
COPY package.json package-lock.json* ./

# Instalujemy zależności
RUN npm install

# Kopiujemy resztę kodu
COPY . .

# Vite domyślnie działa na porcie 5173
EXPOSE 5173

# Uruchamiamy w trybie developerskim z flagą --host,
# aby kontener był dostępny z zewnątrz (ważne w Dockerze!)
CMD ["npm", "run", "dev", "--", "--host"]