# NoSQL-Uzd5

Duomenų bazės modeliavimas. 
**Variantas #6: Kelionių registracijos sistema**
Šioje užduotyje atliekamas duomenų bazės modeliavimas, sukuriamas web servisas, leidžiantis navigacijos įrenginiams registruoti keliones.

Sistemoje registruojasi klientas:
Vardas /
Pavardė
El. pašto adresas
Gimimo data

Klientai registruoja tranporto priemones:
Modelis
Gamintojas
Valstybinis numeris
VIN numeris
Pagaminimo metai

Kliento įrenginys pradėjus kelionę nurodytų automobiliu užregistruoja naują kelionę. Tokiai kelionei kas įrenginyje pasirinktą intervalą (ne mažesnį kaip 5 sekundės) registruoja transporto priemonės koordinates. Baigus kelionę, kelionė pažymima kaip baigta, daugiau pozicijų kelionei nėra registruojama.

Klientai gali peržiūrėti savo keliones. Gauti kelionės trukmę laiku. Gauti kelionės atstumą (kelionės atstumas yra visų atkarpų tarp dviejų iš eilės einančių taškų suma).

Klientai taip pat gali gauti bendrą konkretaus automobilio kelionių trukmę ir atstumą.
