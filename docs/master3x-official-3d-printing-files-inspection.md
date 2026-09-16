# Master3X Official 3D Printing Files Inspection

## 目的

SpeedyBee が公開している `Master3X 3D Printing Files` を実ファイルまで取得し、現在の `speedybee_master3x` Catalog geometry と比較する。

この調査では、公式 STL を **その部品に対する一次 Evidence** として扱う。一方、これらの STL は完成カーボンフレームの CAD ではないため、STL の存在を根拠に Carbon Plate / Arm / Injection-molded Side Plate / Motor-center layout まで拡張解釈しない。

公式ページ: https://docs.speedybee.cn/en/fpv/fpv-drones/master3x-drone/master3x-3d-printing-files.html

調査日: 2026-09-16

## 配布ファイルの範囲

2026-09-16 時点で、公式ページから確認・取得できたものは **17 個の STL** である。STEP / DXF はこのページでは公開されていない。

STL は単位情報、座標系名、軸の意味を保持しない。そのため、以下では native coordinate の数値を記録し、単位は部品寸法との整合から **mm と高い確度で推定**する。

根拠例:

- `Master3X-Motor-Pad` の native bounds は約 `18.0 x 3.5 x 18.0`。
- `Gimbal-camera-limit-stop` は約 `20.70 x 13.34 x 4.0`。

これらを meter と解釈することは不可能であり、inch と解釈しても実機寸法と整合しない。したがって authored coordinates は mm と判断する。ただし **STL 自体に mm が埋め込まれているわけではない**。

## Native bounds / origin / axis inspection

`min/max/extents` は STL の native XYZ 座標。単位は inferred mm。

`Origin` は `(0,0,0)` が AABB 内に入るかどうかを示す。AABB 外のものが多く、raw STL origin を Catalog part origin として使ってはいけない。

`Thin axis` は native AABB の最小 extent 軸であり、意味上の Up 軸を保証しない。実際、Motor Pad は Y が厚み軸、Camera limit stop は Z が厚み軸で、配布 STL 間で orientation は統一されていない。

| # | File | Native min XYZ | Native max XYZ | Extents XYZ | Origin | Thin axis | 対象部品 / 推奨境界 |
|---:|---|---|---|---|---|---|---|
| 1 | Crossfire 915 Receiver Bay | `[-17.522,-67.804,-7.184]` | `[17.522,-17.099,1.507]` | `[35.043,50.705,8.692]` | outside | Z | Receiver carrier → **Frame accessory**。Receiver本体は Electronics |
| 2 | Front Scoop for 915 Receiver | `[-18.924,26.598,-4.000]` | `[18.924,66.800,6.000]` | `[37.848,40.202,10.000]` | outside | Z | Front/nose receiver carrier → **Head accessory**。Receiver本体は Electronics |
| 3 | Nose Bottom Protection Plate | `[-10.646,7.647,-12.500]` | `[10.646,53.672,-4.500]` | `[21.293,46.025,8.000]` | outside | Z | Nose protection → **Head** |
| 4 | Nose GoPro Mount Base | `[-10.700,-15.500,-10.957]` | `[24.127,24.200,5.741]` | `[34.827,39.699,16.698]` | inside | Z | GoPro mounting structure → **Head accessory** |
| 5 | Rear Selfie Mount | `[-15.750,-92.498,-1.909]` | `[15.750,-50.839,32.272]` | `[31.499,41.660,34.180]` | outside | X | Rear mounting structure → **Frame accessory** |
| 6 | Motor Pad | `[-8.999,-1.000,-9.000]` | `[9.000,2.500,8.999]` | `[17.999,3.500,17.999]` | inside | Y | TPU motor protector/pad → **Frame accessory / motor-foot evidence** |
| 7 | Selfie Stick 50/80 mm | `[-5.977,3.000,-33.344]` | `[103.221,8.500,9.716]` | `[109.198,5.500,43.060]` | outside | Y | Removable accessory → **Frame accessory** |
| 8 | Type-A Shark Fin | `[-14.795,-3.407,-20.050]` | `[14.795,36.292,20.835]` | `[29.591,39.700,40.885]` | inside | X | Removable aerodynamic/protection accessory → **Frame accessory** |
| 9 | V-Type Shark Fin | `[-31.410,-14.316,-9.141]` | `[31.580,35.141,19.684]` | `[62.990,49.457,28.825]` | inside | Z | Removable aerodynamic/protection accessory → **Frame accessory** |
| 10 | BEE25 Intake Antenna Mount L | `[21.223,59.745,-7.500]` | `[37.521,94.818,24.544]` | `[16.298,35.073,32.044]` | outside | X | Front/intake antenna carrier → **Head accessory**。Antenna RF elementは Electronics |
| 11 | BEE25 Intake Antenna Mount R | `[54.479,58.745,-7.500]` | `[70.777,93.818,24.544]` | `[16.298,35.073,32.044]` | outside | X | Front/intake antenna carrier → **Head accessory**。Antenna RF elementは Electronics |
| 12 | 121 GPS Printed Part | `[-15.750,-10.294,1.556]` | `[15.750,27.351,22.499]` | `[31.500,37.645,20.943]` | outside | Z | GPS carrier → **Frame accessory**。GPS moduleは Electronics |
| 13 | 181 GPS | `[84.250,-92.498,-1.909]` | `[115.750,-50.839,21.000]` | `[31.499,41.660,22.909]` | outside | Z | GPS carrier → **Frame accessory**。GPS moduleは Electronics |
| 14 | Front Scoop for 2.4G Receiver | `[-18.924,26.598,-4.000]` | `[18.924,66.800,6.000]` | `[37.848,40.202,10.000]` | outside | Z | Front/nose receiver carrier → **Head accessory**。Receiver本体は Electronics |
| 15 | O4P Nose Cone Antenna Sleeve | `[15.501,130.542,19.471]` | `[22.439,137.545,31.932]` | `[6.938,7.003,12.461]` | outside | X | O4P nose antenna sleeve → **Head accessory** |
| 16 | Gimbal Camera Limit Stop | `[0.000,0.003,0.000]` | `[20.700,13.338,4.000]` | `[20.700,13.335,4.000]` | corner | Z | O4 Pro camera retention/protection → **Head**, not Camera |
| 17 | O4WA Updated Antenna Mount TPU | `[0.000,22.554,151.783]` | `[17.008,65.148,173.723]` | `[17.008,42.594,21.939]` | outside | X | O4WA antenna carrier → **Head accessory**。Antenna本体は Electronics |

## Origin / axis conclusion

raw STL の `origin` と native axes は Catalog local frame に直接流用しない。

理由:

1. `(0,0,0)` が mesh bounds 外にあるファイルが多数ある。
2. L/R pair でも絶対座標が大きく異なる。
3. 厚み軸が Motor Pad では Y、Camera Limit Stop では Z であり、orientation が統一されていない。
4. STL format 自体に semantic axis / unit / named datum が存在しない。

Catalog へ取り込む場合は、各部品の **mounting interface を datum** として local frame を作り直し、その後 meter へ変換する。

## 現在の `speedybee_master3x` YAML との差分

### Core Frame

17 STL の中に、以下の完成形状 CAD は存在しない。

- Top / Middle / Bottom carbon plate
- Arm
- Injection-molded Side Plate
- Main Front Support / structural camera cage
- four motor-center layout

したがって、現在の YAML の plate planform / arm layout / yellow tapered side-body を、これら STL で置き換える根拠は得られない。PR #11–#13 で分離した Evidence Matrix + photo inference は引き続き必要。

### Motor foot / pad

現在の YAML は、各 motor center に:

- yellow `foot_*`: cylinder, diameter `21 mm`, thickness `4 mm`
- dark `motor_pad_*`: cylinder, diameter `20 mm`, thickness `4 mm`

を置いている。

公式 `Master3X-Motor-Pad(TPU,M2_10).stl` の envelope は約:

```text
18.0 x 18.0 mm footprint
3.5 mm thickness
```

である。したがって現在の yellow foot proxy は optional TPU pad より:

- footprint diameter/envelope: 約 16.7% 大きい (`21 / 18`)
- thickness: 約 14.3% 大きい (`4 / 3.5`)
- topology: circular proxy vs actual shaped TPU part

という差がある。

ただしこの STL は **3D-printing accessory / replacement part** であり、標準装着の injection-molded motor pad と同一寸法であることまでは一次資料から保証できない。このため default Frame の `foot_*` を自動置換せず、将来 `Master3X TPU Motor Pad` accessory variant を作る際の一次 Evidence とする。

### Head

Nose protection, GoPro base, receiver front scoop, intake antenna mounts, O4P antenna sleeve, O4WA antenna mount, Camera limit stop はすべて Head / nose 周辺の variant-specific accessories と解釈する。

特に公式ページは `Gimbal-camera-limit-stop` について O4 Pro camera を M2x4 screw で固定し、クラッシュ時に camera が飛び出すのを防ぐ protection part と説明している。したがってこれは Camera intrinsic geometry ではなく **Head-side retention structure** である。

### Camera

17 STL の中に camera body / lens / camera chassis の CAD はない。

よって現在の `master3x_demo_camera_head` の camera case / lens geometry をこれら STL で寸法確定することはできない。Camera Catalog item は引き続き **camera intrinsic rigid body only** とする。

### Electronics

Receiver bay, GPS printed part, antenna mount は Electronics そのものではない。

- active Receiver / GPS / VTX / RF antenna → **Electronics**
- それを機体へ固定する TPU/CNC carrier → **Frame accessory または Head accessory**

という境界にする。

## Revised boundary

### Frame

常設の機体構造:

- carbon plates / arms
- standoffs
- injection-molded side structure
- motor-foot / arm protection when treated as standard frame hardware
- rear/top removable structural accessories when selected

### Head

nose/front の交換可能 structural module と保持部品:

- front/nose protection
- camera cage / camera retention
- front receiver scoop
- GoPro nose base
- O4P/O4WA antenna sleeve/mount
- intake antenna mounts

### Camera

camera intrinsic rigid body only:

- camera chassis/case
- lens / optical center
- camera-intrinsic mount ears only

`Gimbal-camera-limit-stop` は Camera に含めない。

### Electronics

active electronics only:

- AIO / FC / ESC
- VTX
- Receiver
- GPS
- RF antenna electrical element

TPU/CNC holder は Electronics に含めない。

## GLB policy

公式 STL を raw mesh として Catalog repo へ再配布しない。まず measurement evidence として使い、Catalog には normalized dimensions / interface / provenance を記録する。

今回の STL set は core-frame CAD を提供していないため、default `speedybee_master3x` geometry の core shape は変更しない。GLB は現行 Evidence Matrix + photo-inferred side-body の状態を baseline として再生成し、今後 variant-specific accessory Catalog を追加した際に差分比較する。

## SHA-256

取得した ZIP artifact および個別 STL の SHA-256 は調査成果物側の `SHA256SUMS.txt` / inspection CSV に保存する。外部 mesh 自体は repository にコミットしない。
