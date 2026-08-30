# Recipe仕様 v1 / v2

Recipeはユーザーが作りたい一台の機体を表し、Catalog IDを参照します。

```yaml
schema_version: 1
name: example-5inch-fpv
type: quad_x
components:
  frame: generic_5inch_x
  motors:
    product: generic_2207_1850kv
    count: 4
  propeller: generic_5inch_3blade
  battery: generic_6s_1300mah
  camera: generic_fpv_camera
controller:
  product: hakoniwa_default
  mode: angle
placements:
  battery_m: [0.0, 0.0, 0.025]
  camera_m: [0.080, 0.0, 0.005]
  controller_m: [0.0, 0.0, 0.005]
```

## 座標系

MVPのRecipe座標は機体body座標です。

- +X: 前方
- +Y: 左方
- +Z: 上方
- 単位: meter

`placements` は部品の取付位置・姿勢です。v2のCOMと慣性は配置されたinertial geometryからMuJoCoが導出します。Camera位置はMuJoCo cameraおよびThree.js向けメタデータにも渡します。

## 制約

- v1の`quad_x`はmotor count 4固定
- v2の`multirotor`は可変数。frame Catalogに同数の`motor_mount_positions_m`、Recipeに同数の明示`rotor_layout`が必須。最大数は公開スキーマに複製せずDrone PRO contractで検証
- modeは `angle` または `rate`
- 参照先IDが存在し、Controllerがmodeをsupportする必要がある

未知のmetadataや将来拡張キーは許容します。物理的に必要な値が不足した場合、Catalog resolverはエラーにし、根拠のない値を黙って生成しません。

## v2: landing gearとattachment

v2はv1の必須部品を保ったまま、着陸装置と任意個の取付部品を追加します。

```yaml
schema_version: 2
components:
  frame: generic_utility_quad_frame
  motors: {product: generic_motor, count: 4}
  propeller: generic_propeller
  battery: generic_battery
  camera: generic_camera
  landing_gear: generic_quad_skid

placements:
  landing_gear:
    position_m: [0.0, 0.0, 0.0]
    rpy_deg: [0.0, 0.0, 0.0]

attachments:
  - name: telemetry_antenna
    product: generic_antenna
    parent: frame
    position_m: [-0.06, 0.04, 0.03]
    rpy_deg: [0.0, 15.0, 0.0]
```

attachmentの`name`は一台のRecipe内で一意です。同じCatalog製品を複数回、異なるnameと取付姿勢で利用できます。初版の`parent`は`frame`だけを許可し、それ以外は明示的に拒否します。

## v2: 初期接地高さ

v2では固定の初期Zを使わず、全collision primitiveの最下点から機体bodyの初期Zを自動計算します。追加の隙間だけを指定できます。

```yaml
initial_pose:
  ground_clearance_m: 0.01
```

省略値は1cmです。v1は生成互換性のため従来のMuJoCo Z=0.25mを維持します。

v1 Recipeは変更なしで読み込めます。landing gearとattachmentsを省略した場合は従来生成経路になります。

## 可変ローター機

Drone PROのgeneric control allocationへ渡す機体では、ローター位置・順序・回転方向をRecipeの`rotor_layout`へ明示します。意味上の正本はHakoniwa Drone PROの`components.thruster.rotorPositions`契約です。

```yaml
schema_version: 2
name: example-hexa
type: multirotor
components:
  motors: {product: generic_motor, count: 6}
rotor_layout:
  contract: hakoniwa-drone-pro/rotor-layout-v1
  rotors:
    - name: prop1
      position_flu_m: [0.25, 0.0, 0.0]
      rotation_direction: 1
    # ... prop6まで同じ順序で記述
```

Generatorは各entryを同じindexでMuJoCo `propNames`へ出力し、同梱されたDrone PRO target contractの変換行列に従ってFRD `rotorPositions`を生成します。座標変換をRecipe作者へ重複記述させません。

Drone PRO契約上、FRDは`+X Forward, +Y Right, +Z Down`、`rotation_direction=+1`は上から見てCCW、`-1`はCWです。公開Generatorはこの意味を再定義せず、指定されたcontract versionに従うadapterです。
