# FPV World / Course

機体の部品構成と飛行場所は別の設計対象です。Vehicle Recipeは一台の機体を定義し、World YAMLはMuJoCoの背景、照明、地面、FPVコース障害物を定義します。

既定のコースは `recipes/environments/fpv-training-course.yaml` です。次のコマンドで機体と合成します。

```bash
fpv-drone generate recipes/examples/5inch-fpv.yaml \
  --world recipes/environments/fpv-training-course.yaml \
  --output build/example-5inch
```

Drone PROを使う場合は、同じWorld YAMLが`configure`の既定値です。

```bash
python3.12 tools/fpv.py configure
python3.12 tools/fpv.py start
```

別コースは`--world`で指定します。

```bash
python3.12 tools/fpv.py configure --world recipes/environments/my-course.yaml
```

## 障害物

初期版は次の3種類です。

- `gate`: 中央が空いた4本のboxからなるFPVゲート。`center_m`は開口中央です。
- `pylon`: 垂直なcylinder。`center_m`は円柱中央です。
- `box`: 壁、低いバー、タワー等。`dimensions_m`は全寸法です。

座標はMuJoCo world座標のmeter、角度はworld +Z周りのdegreeです。すべて物理collisionを持つため、単なる背景ではありません。

## 明るさ

`visual`で空・霞・Viewerのheadlightを、`lights`で固定照明を、`ground`で地面の大きさと色を変更できます。既定値は屋外の明るい練習場を意図しています。

## 接触と摩擦

`contact`は地面、機体、コース障害物の摩擦を個別に指定します。既定コースは離着陸に必要な地面摩擦を保ちながら、機体と障害物を低摩擦にしています。Angle/Hover制御の推力で壁へ押し付けられた機体が、摩擦で張り付く現象を抑えるためです。

```yaml
contact:
  ground_friction: [0.80, 0.02, 0.001]
  vehicle_friction: [0.15, 0.002, 0.0001]
  obstacle_friction: [0.15, 0.002, 0.0001]
  obstacle_condim: 3
```

MuJoCoの接触は両方のgeom設定を使うため、障害物だけでなく機体側も低摩擦にしています。`obstacle_condim: 1`とすれば障害物の接線摩擦をなくせますが、まずは`3`のまま摩擦を下げる方針です。

## 主観カメラ

生成機体には`fpv`固定カラが含まれます。FPV runtimeはDrone PROを`--mujoco-fpv-pip`付きで起動し、主観カラを全面、操作可能な客観カラを左上の16:9 PiPとして表示します。`Tab`キーで主画面とPiPを交換し、`F`キーでPiPを表示・非表示できます。このオプションを指定しない通常のDrone PRO Viewerには影響しません。
