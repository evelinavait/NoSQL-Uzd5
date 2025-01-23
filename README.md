# NoSQL-Uzd5

Duomenų bazės modeliavimas. **Variantas #6: Kelionių registracijos sistema**

Šioje užduotyje atliekamas duomenų bazės modeliavimas, pagal sudarytą API aprašą sukuriamas web servisas, leidžiantis navigacijos įrenginiams registruoti keliones.

Sistemoje registruojasi klientas:
- Vardas  
- Pavardė  
- El. pašto adresas  
- Gimimo data  

Klientai registruoja transporto priemones:
- Modelis
- Gamintojas
- Valstybinis numeris
- VIN numeris
- Pagaminimo metai

Kliento įrenginys pradėjus kelionę nurodytų automobiliu užregistruoja naują kelionę. Tokiai kelionei kas įrenginyje pasirinktą intervalą (ne mažesnį kaip 5 sekundės) registruoja transporto priemonės koordinates. Baigus kelionę, kelionė pažymima kaip baigta, daugiau pozicijų kelionei nėra registruojama.

Klientai gali peržiūrėti savo keliones. Gauti kelionės trukmę laiku. Gauti kelionės atstumą (kelionės atstumas yra visų atkarpų tarp dviejų iš eilės einančių taškų suma).

Klientai taip pat gali gauti bendrą konkretaus automobilio kelionių trukmę ir atstumą.

## Duomenų bazės struktūros diagrama
<p align="center">
  <img alt="Image of ERD" src="https://raw.githubusercontent.com/evelinavait/NoSQL-Uzd5/master/images/ER-diagram.png" />
</p>

## Routes and Resources
### Klientai Resource
|URL|HTTP metodas|Resultatas|
|---|---|---|
/clients|PUT|Užregistruoti klientą sistemoje|
/clients/{clientId}|GET|Gauti kliento duomenis|

### Transporto priemonės Resource
|URL|HTTP metodas|Resultatas|
|---|---|---|
/vehicles|PUT|Registruoti naują priemonę|
/clients/{client_id}/vehicles|GET|Gauti kliento transporto priemones|
/vehicles/{vehicle_id}/statistics|GET|Gauti bendrą kelionių statistiką|

### Kelionės Resource
|URL|HTTP metodas|Resultatas|
|---|---|---|
/journeys|PUT|Pradėti naują kelionę|
/journeys/{journey_id}/coordinates|POST|Registruoti transporto priemonės koordinates|
/journeys/{journey_id}|GET|Gauti kelionės informaciją|
/journeys/{journey_id}/end|PUT|Baigti kelionę|

### Duomenų bazės valymas
|URL|HTTP metodas|Resultatas|
|---|---|---|
/cleanup|POST|Išvalyti duomenų bazę|

---
`redocly build-docs openapi.yaml --output docs/index.html`





