import os

SESAMATH_URL_FORMAT = "https://mathenpoche.sesamath.net/?page={0}"

SESAMATH_THUMBNAIL_PATH = os.path.join("files", "sesamath_logo.png")

GRADE_MAP = [
  "https://mathenpoche.sesamath.net/?page=sixieme",
  "https://mathenpoche.sesamath.net/?page=cinquieme",
  "https://mathenpoche.sesamath.net/?page=quatrieme",
  "https://mathenpoche.sesamath.net/?page=troisieme",
  "https://mathenpoche.sesamath.net/?page=seconde",
  "https://mathenpoche.sesamath.net/?page=premiere",
  "https://mathenpoche.sesamath.net/?page=terminale"
]

MATH_MANUELS = {
  "Sixième":{
    "Manuel Sésamath 6e": "https://manuel.sesamath.net/send_file.php?file=/files/ms6_2013.pdf",
    "Cahier Sésamath 6e": "https://manuel.sesamath.net/send_file.php?file=/files/cs6_2015.pdf",
    "Cahier de Cycle 3 - 6e": "https://manuel.sesamath.net/send_file.php?file=/files/cahier_2017_cycle3_6e.pdf"
  },
  "Cinquième":{
    "Manuel Sésamath 5e": "https://manuel.sesamath.net/send_file.php?file=/files/ms5_2010.pdf",
    "Cahier Sésamath 5e": "https://manuel.sesamath.net/send_file.php?file=/files/cs5_2010.pdf",
    "Cahier Sésamath Cycle 4 - 5e": "https://manuel.sesamath.net/send_file.php?file=/files/cahier_2017_cycle4_5e.pdf"
  },
  "Quatrième": {
    "Manuel Sésamath 4e": "https://manuel.sesamath.net/send_file.php?file=/files/ms4_2011.pdf",
    "Cahier Sésamath 4e": "https://manuel.sesamath.net/send_file.php?file=/files/cs4_2011.pdf",
    "Cahier Sésamath Cycle 4 - 4e (édition 2017)": "https://manuel.sesamath.net/send_file.php?file=/files/cahier_2017_cycle4_4e.pdf"
  },
  "Troisième":{
    "Manuel Sésamath 3e": "https://manuel.sesamath.net/send_file.php?file=/files/ms3_2012.pdf",
    "Cahier Sésamath 3e": "https://manuel.sesamath.net/send_file.php?file=/files/cs3_2012.pdf",
    "Cahier Sésamath Cycle 4 - 3e (édition 2017)": "https://manuel.sesamath.net/send_file.php?file=/files/cahier_2017_cycle4_3e.pdf",
    "Fichier d’exercices CFG mathématiques": "https://manuel.sesamath.net/docs/fichierCFG_2009.pdf"
  },
  "Seconde":{
    "Manuel Magnard 2nde": "https://manuel.sesamath.net/send_file.php?file=/files/ms2_2019_v3.pdf",
    "Cahier 2nde Professionnelle": "https://manuel.sesamath.net/send_file.php?file=/files/lp2_2014.pdf"
  },
  "Première":{
    "Manuel Magnard 1ère": "https://manuel.sesamath.net/send_file.php?file=/files/ms1spe_2019_v3.pdf"
  }
}

ADDITIONAL_MANUELS = {
  "Manuel de Cycle 4 Presentation": "https://manuel.sesamath.net/docs/manuel_cycle4_presentation.pdf",
  "Manuel Cycle 4": "https://manuel.sesamath.net/send_file.php?file=/files/cycle4_2016_v2.pdf"
}