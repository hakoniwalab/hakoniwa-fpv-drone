# Recipe仕様 v1

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

`placements` は質量・重心・慣性計算に使います。Camera位置はMuJoCo cameraおよびThree.js向けメタデータにも渡します。

## 制約

- `type` は `quad_x` のみ
- motor countは4固定
- modeは `angle` または `rate`
- 参照先IDが存在し、Controllerがmodeをsupportする必要がある

未知のmetadataや将来拡張キーは許容します。物理的に必要な値が不足した場合、Catalog resolverはエラーにし、根拠のない値を黙って生成しません。
