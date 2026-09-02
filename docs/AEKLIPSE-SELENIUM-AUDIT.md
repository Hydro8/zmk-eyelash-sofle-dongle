# Æklipse — Audit baseline firmware Selenium

Baseline auditée : `selenium@523bd65121277fe7503ca9f83efae7c6f91fd11e`  
Branche de travail : `aeklipse/selenium-adoption-p1`  
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

Le mécanisme existant est donc précieux comme baseline matérielle réellement fonctionnelle, mais le protocole n'est pas encore conforme au contrat Æklipse v0-DRAFT.

## Dépendances West / reproductibilité

Toutes les dépendances custom observées dans `config/west.yml` utilisent encore `revision: main` :

- `keebs34/zmk-config-selenium` ;
- `GPeye/mario-peripheral-animation` ;
- `zmkfirmware/zmk` ;
- `cormoran/zmk-behavior-runtime-sensor-rotate` ;
- `cormoran/zmk-module-ble-management` ;
- `cormoran/zmk-module-battery-history` ;
- `cormoran/zmk-module-runtime-input-processor` ;
- `Hydro8/zmk-dongle-display` ;
- `zzeneg/zmk-raw-hid`.

Cela rend une reconstruction future non déterministe. La priorité P1 est de capturer les commits exacts actuellement compatibles, puis de remplacer progressivement ces branches mouvantes par des SHAs immuables après build local des quatre targets.

Premières révisions vérifiées au moment de l'audit :

- `zmkfirmware/zmk`: `641514a97db345f499dd50b0360e594270f008fe` ;
- `keebs34/zmk-config-selenium`: `a3ec3d1f0bdd7d0bbd4df95b0517379ad3e336a6` ;
- `Hydro8/zmk-dongle-display`: `1e68660e534b2c8d5be008f0f6984cd595fbc827`.

Ces SHAs sont documentés mais ne sont pas encore tous appliqués au manifest tant que le build local complet n'a pas validé l'ensemble cohérent des modules.

## Build local hors GitHub Actions

Le workflow historique `.github/workflows/build.yml` est conservé pour traçabilité, mais il n'est plus une preuve canonique Æklipse conformément à `DEC-20260902-007`.

Le script `scripts/build-local-aeklipse.sh` reproduit localement le chemin principal du workflow existant : `west init -l config`, `west update`, puis builds des quatre entrées de `build.yaml` avec `BOARD_ROOT` et `ZMK_CONFIG` explicites.

La validation canonique future doit exécuter ce script dans une toolchain ZMK locale/container externe à GitHub Actions et archiver les commandes + HEADs effectivement utilisés.

## Nettoyage dépôt

`.gitignore` ignore déjà `.DS_Store`, mais plusieurs fichiers `.DS_Store` sont suivis dans Git. Ils sont parasites et peuvent être retirés de la branche de modernisation sans effet fonctionnel. Aucun doublon de shield n'est supprimé à ce stade.

## Risques classés

### P0

- protocole Raw HID historique sans version/capabilities/session/validation robuste ;
- index ZMK exposé directement au desktop au lieu d'un `layer_id` logique ;
- état remonté réduit au highest layer, incompatible avec le snapshot multi-layer P0 ;
- dépendances West mouvantes sur `main`.

### P1

- build local des quatre targets à démontrer après pinning ;
- ownership des layers Smart App à revalider dans `app_layer_sync.c` / `behavior_app_layer.c` ;
- reconnexion/perte de session à formaliser ;
- flash/RAM et stabilité BLE split à mesurer sur builds réels ;
- placeholders N0/N1 à remplacer par bindings produit validés.

### P2

- déduplication `eyelash_sofle` / `eyeslash_solfe` ;
- nettoyage docs/commentaires obsolètes et artefacts parasites ;
- optimisation consommation batterie et instrumentation diagnostics.

## Séquence minimale recommandée

1. prouver le build local de la baseline inchangée ;
2. capturer/pinner toutes les dépendances au set exact qui vient de passer ;
3. ajouter framing/version/validation au Raw HID sans changer les comportements clavier ;
4. introduire mapping `layer_id` logique ↔ index ZMK ;
5. enrichir le state reporting vers active set + highest + Smart App selected ;
6. seulement ensuite moderniser les Smart App Layers et l'overlay ;
7. dédupliquer/nettoyer le dépôt dans des commits séparés de la logique.

## UNKNOWN / gates matériels

- aucun flash matériel n'a été exécuté pendant cet audit ;
- stabilité BLE des deux périphériques non requalifiée ici ;
- consommation batterie non mesurée ;
- flash/RAM non mesurés ;
- compatibilité du set de HEADs `main` actuel après pinning complet doit être prouvée par build local avant modification fonctionnelle.
