# Æklipse — Audit baseline firmware Selenium

Baseline auditée : `selenium@523bd65121277fe7503ca9f83efae7c6f91fd11e`  
Branche de travail : `aeklipse/selenium-adoption-p1`  
Baseline reproductible validée : `49070f9f340b2fb7a01fca504def647f58ed7865`  
Date : 2026-09-02

## Architecture réellement observée

- `build.yaml` définit quatre builds : `settings_reset`, dongle central USB, périphérique gauche BLE, périphérique droit BLE.
- Le dongle central utilise `nice_nano@2` avec les shields `eyelash_sofle_central_dongle`, `dongle_display` et `raw_hid_adapter`.
- Les deux moitiés utilisent `nice_nano@2` avec `eyelash_sofle_peripheral_left/right`.
- Le dépôt contient deux arbres de shield proches : `boards/shields/eyelash_sofle` et `boards/shields/eyeslash_solfe`.
- Le chemin actif est `eyelash_sofle`, car c'est celui référencé par `build.yaml` et par `config/eyelash_sofle.*`. `eyeslash_solfe` est donc un doublon historique/inactif à ne pas supprimer avant comparaison complète.

## Keymap et Smart App Layers

La keymap produit réellement utilisée est `config/eyelash_sofle.keymap`.

Elle contient :

- le comportement `&app_layer` sur le cluster pouce ;
- un node `app_layer_config` avec `auto-layers = <10>` ;
- les layers applicatifs 7 `Autocad`, 8 `Word`, 9 `Excel`, 10 `Calc` ;
- les layers 7–9 sont majoritairement des placeholders `N0/N1` ; le layer 10 contient un début de pavé numérique réel.

Le numéro de layer utilisé aujourd'hui par le firmware est un index ZMK concret. Il ne doit pas être confondu avec le `layer_id` logique stable défini par `LAYER-MODEL P0-DRAFT`. Une table de mapping explicite devra être introduite avant que le desktop persiste ces identités comme contrat produit.

## Chemin App Layer / Raw HID actuel

`zmk-dongle-display` fournit `app_layer_sync.c` et `behavior_app_layer.c`; `zmk-raw-hid` fournit le transport Raw HID 32 octets.

Le protocole effectif observé dans `app_layer_sync.c` est historique et plus simple que `HID-PROTOCOL v0-DRAFT` :

- Mac → clavier : `byte[0]=layer index`, `byte[1]=auto`, `byte[2]=one-shot`, `byte[3..]=app name` ;
- clavier → Mac : `byte[0]=zmk_keymap_highest_layer_active()` ;
- pas de négociation de version/capabilities ;
- pas de séquence ACK/NACK ;
- pas de session explicite ;
- pas de snapshot multi-layer ;
- l'identité transportée est l'index ZMK, pas un `layer_id` logique.

Risques techniques importants :

1. le parsing lit directement `ev->data[0..2]`; une validation explicite de longueur/version doit être ajoutée au futur binding Æklipse ;
2. l'état envoyé au Mac est uniquement le highest active layer et ne transporte ni `active_layer_ids` ni `smart_app_selected_layer_id` ;
3. `app_layer_sync.c` désactive l'ancien app layer avec le chemin de force actuel ; cette logique doit être revalidée contre l'invariant P0 « domaine Smart App isolé » pour ne jamais détruire une activation appartenant à un autre domaine ;
4. `current_app_layer` et `active_app_layer` restent des indexes ZMK bruts ; un mapping stable est requis.

Le mécanisme existant est donc conservé comme baseline matérielle réellement fonctionnelle, mais le protocole n'est pas encore conforme au contrat Æklipse v0-DRAFT.

## Dépendances West / reproductibilité

Les neuf dépendances directes auparavant mouvantes sur `main` ont été figées dans `config/west.yml` sur le set exact ayant passé deux fois les quatre builds locaux :

- `zmk-config-selenium`: `a3ec3d1f0bdd7d0bbd4df95b0517379ad3e336a6`
- `mario-peripheral-animation`: `1aa3950d6c86b4240b3f79d06bdbb04c5d920711`
- `zmk`: `641514a97db345f499dd50b0360e594270f008fe`
- `zmk-behavior-runtime-sensor-rotate`: `8b1125ed676c1f5e14145d217984f33d0ebdcef4`
- `zmk-module-ble-management`: `57738cc4fc6ba80e82a7ac57741a0339cb186cd4`
- `zmk-module-battery-history`: `307755dd2ad4d320e14de162e8e5ef018f29d929`
- `zmk-module-runtime-input-processor`: `43618985f8c9d5457cc333b7ca0733f2d361911e`
- `zmk-dongle-display`: `1e68660e534b2c8d5be008f0f6984cd595fbc827`
- `zmk-raw-hid`: `6a37765dfab6197292e7a9f47305dcf87386d56a`

Les dépendances transitives Zephyr restent déterminées par l'import du commit ZMK figé. Le build observé résout notamment Zephyr `v4.1.0+zmk-fixes` sur `10ba6d0cb38b...`.

## Build local hors GitHub Actions

Le workflow historique `.github/workflows/build.yml` est conservé pour traçabilité, mais il n'est plus une preuve canonique Æklipse conformément à `DEC-20260902-007`.

Le script `scripts/build-local-aeklipse.sh` exécute `west update` puis les quatre entrées de `build.yaml` avec `BOARD_ROOT` et `ZMK_CONFIG` explicites.

### Toolchain qualifiée le 2 septembre 2026

- macOS Apple Silicon ;
- Python `3.12.14` dans un environnement virtuel dédié ;
- CMake `3.31.10` ;
- West `1.5.0` ;
- Zephyr SDK `0.17.0` ;
- toolchain `arm-zephyr-eabi` GCC `12.2.0`.

### Première preuve avant pinning

Les quatre cibles ont compilé localement avec succès sur le set de HEADs ensuite figé.

### Revalidation après pinning — PASS

Commande canonique : `PATH="$VENV/bin:$PATH" bash scripts/build-local-aeklipse.sh`.

HEAD firmware vérifié avant lancement : `49070f9f340b2fb7a01fca504def647f58ed7865`.

Résultats :

- `settings-reset` : PASS — Flash `43,752 B / 792 KB` (5.39 %), RAM `12,448 B / 256 KB` (4.75 %), UF2 `87,552 B` ;
- `central-dongle` : PASS — Flash `410,148 B / 792 KB` (50.57 %), RAM `87,228 B / 256 KB` (33.27 %), UF2 `820,736 B` ;
- `peripheral-left` : PASS — Flash `185,156 B / 792 KB` (22.83 %), RAM `37,848 B / 256 KB` (14.44 %), UF2 `370,688 B` ;
- `peripheral-right` : PASS — Flash `184,712 B / 792 KB` (22.78 %), RAM `37,864 B / 256 KB` (14.44 %), UF2 `369,664 B`.

Le script termine par `PASS: four Selenium targets built locally outside GitHub Actions`.

Les warnings de compilation sont conservés comme dette technique, notamment `KSCAN` déprécié, options Studio inactives, vendor prefix `app`, plusieurs warnings de modules runtime et incompatibilités de type LVGL dans le display. Aucun n'empêche actuellement le link ni la génération UF2. Les warnings de bounds observés dans le target `settings-reset` doivent être traités comme risque de maintenance ZMK, mais ne sont pas une preuve d'un défaut produit des trois firmwares opérationnels.

## Nettoyage dépôt

`.gitignore` ignore déjà `.DS_Store`. Le `.DS_Store` racine suivi a été supprimé sur la branche de travail. D'autres artefacts historiques restent candidats à un nettoyage séparé. Aucun doublon de shield n'est supprimé à ce stade.

## Risques classés après adoption

### P0

- protocole Raw HID historique sans version/capabilities/session/validation robuste ;
- index ZMK exposé directement au desktop au lieu d'un `layer_id` logique ;
- état remonté réduit au highest layer, incompatible avec le snapshot multi-layer P0.

Le risque P0 de dépendances West directes mouvantes est levé sur la branche d'adoption par le pinning validé.

### P1

- ownership des layers Smart App à revalider dans `app_layer_sync.c` / `behavior_app_layer.c` ;
- reconnexion/perte de session à formaliser ;
- stabilité BLE split à requalifier matériellement ;
- warnings Kconfig/LVGL/ZMK à résorber sans changement de comportement ;
- placeholders N0/N1 à remplacer par bindings produit validés.

### P2

- déduplication `eyelash_sofle` / `eyeslash_solfe` ;
- nettoyage docs/commentaires obsolètes et artefacts parasites ;
- optimisation consommation batterie et instrumentation diagnostics.

## Séquence minimale recommandée

1. conserver `49070f9f...` comme baseline reproductible d'adoption ;
2. ajouter framing/version/validation au Raw HID sans changer les comportements clavier ;
3. introduire mapping `layer_id` logique ↔ index ZMK ;
4. enrichir le state reporting vers active set + highest + Smart App selected ;
5. revalider l'ownership Smart App Layers ;
6. remplacer les placeholders applicatifs après validation produit ;
7. traiter warnings et nettoyage dans des commits séparés de la logique ;
8. exécuter ensuite les gates matériels BLE/reconnexion/batterie/flash réel.

## Éléments conservés

- architecture dongle central USB + deux périphériques BLE ;
- boards/shields actifs `eyelash_sofle` ;
- display et pointing existants ;
- keymap Selenium réelle ;
- Smart App Layers existants comme baseline comportementale ;
- `zmk-dongle-display` et `zmk-raw-hid` comme point de départ ;
- workflow GitHub historique uniquement pour traçabilité.

## Éléments corrigés pendant l'adoption

- procédure locale de build des quatre targets ;
- correction du script de build pour positionner correctement le répertoire `west build` avant les arguments CMake ;
- pinning des neuf dépendances West directes auparavant mouvantes ;
- suppression sûre du `.DS_Store` racine ;
- documentation d'audit et des gates.

## UNKNOWN / gates matériels

- aucun flash matériel n'a été exécuté pendant cet audit ;
- stabilité BLE des deux périphériques non requalifiée matériellement ;
- reconnexion/perte de session non requalifiée matériellement ;
- consommation batterie non mesurée ;
- comportement Raw HID réel avec l'application macOS future non requalifié ici.

Ces UNKNOWN ne bloquent pas l'adoption P1 de la baseline reproductible ; ils restent des gates des étapes d'intégration suivantes.
