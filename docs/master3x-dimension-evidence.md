# Master3X Dimension Evidence Matrix

## 目的

`speedybee_master3x` の剛体geometryを実機へ寄せる前に、各寸法について「何が分かっていて、何がまだ分かっていないか」を出典と横並びで管理する。

この文書の目的は、推定値をゼロにすることではない。**一次資料・計測・導出で確定できる値を先に埋め、どうしても推定が必要な値だけを、根拠・計算方法・不確かさ付きで残すこと**である。

次のgeometry変更PRは、このEvidence Matrixを入力として行う。YAMLの数値を先に変えてから理由を後付けしない。

## Evidence分類

| 種別 | 意味 | 扱い |
| --- | --- | --- |
| `manufacturer` | メーカー一次資料に数値または構造が明示されている | 原則そのまま採用可能 |
| `measured` | メーカー配布物・実物等から寸法を計測した | 計測対象、単位、方法を記録して採用 |
| `corroborated` | 一次資料で機械可読な数値を確認できないが、複数の信頼できる販売資料等で同じ仕様が一致する | 一次資料の目視確認までは暫定確定扱い |
| `derived` | 確定した入力値から式で一意に導出できる | 式と入力値を必ず記録 |
| `inferred` | 写真、組立図、既知寸法との比率などから推定する | 根拠、計算法、想定誤差を必ず記録 |
| `estimated` | 直接根拠がなく、典型値や見た目整合性から仮置きする | 一時値。置換候補として管理 |
| `unknown` | 現在の資料では決められない | 勝手に確定値へ昇格させない |

`derived` と `inferred` は区別する。例えば `171 / (2*sqrt(2))` は数学的には正しい導出だが、「実機が正方形True-Xである」という未確認仮定を含むため、実機geometryとしては `inferred` 相当の不確かさを残す。

## Source index

### Primary / manufacturer

- `S1` SpeedyBee Master3X Frame product page  
  https://www.speedybee.com/speedybee-master3x-frame/
- `S2` Master 3X Frame Download  
  https://www.speedybee.com/master3x-frame-download/
- `S3` Master 3X Frame Installation, SpeedyBee Knowledge Base  
  https://docs.speedybee.cn/en/fpv/frame/master-3x-frame/master-3x-frame-installation.html
- `S4` Master 3X Frame Installation PDF  
  https://spcdn.speedybee.cn/cdn/142107666636869632.pdf?attname=sbee_master3x_frame_manual-en.pdf
- `S5` SpeedyBee Master3X Drone product page  
  https://www.speedybee.com/speedybee-master3x-drone/
- `S6` Accessories for SpeedyBee Master 3X  
  https://www.speedybee.com/accessories-for-speedybee-master-3x/
- `S7` Master3X 3D Printing Files  
  https://docs.speedybee.cn/en/fpv/fpv-drones/master3x-drone/master3x-3d-printing-files.html
- `S8` Master3X 3D Printed Parts Installation Guide  
  https://docs.speedybee.cn/en/fpv/fpv-drones/master3x-drone/master3x-3d-printed-parts-installation-guide.html

### Secondary corroboration

- `S9` RaceDayQuads Master3X frame specification  
  https://www.racedayquads.com/products/speedybee-master3x-modular-3-3-6-frame-kit
- `S10` FPV24 Master3X frame specification  
  https://www.fpv24.com/en/speedy-bee/speedybee-master-3x-3-inch-fpv-frame
- `S11` Team BlackSheep Master3X frame specification  
  https://www.team-blacksheep.com/products/product:8434

Secondary sourceは一次資料の代替ではない。公式製品ページのspec画像等を人手で確認できた時点で、対応する項目は `manufacturer` へ昇格する。

## Confirmed / corroborated dimensions

| 項目 | 値 | Evidence | 出典 | 根拠・備考 | Confidence | YAML反映先 |
| --- | ---: | --- | --- | --- | --- | --- |
| Wheelbase | 171 mm | `corroborated` | S1, S9, S10, S11 | S1は製品識別一次資料。171 mmは複数販売仕様で一致。公式spec画像の目視確認後に`manufacturer`へ昇格する | High | `wheelbase_m` |
| Top plate thickness | 2.0 mm | `corroborated` | S9, S10, S11 | 複数仕様で一致 | High | `geometry.visual` |
| Middle plate thickness | 2.0 mm | `corroborated` | S9, S10, S11 | 複数仕様で一致 | High | `geometry.visual` |
| Bottom plate thickness | 2.0 mm | `corroborated` | S9, S10, S11 | 複数仕様で一致 | High | `geometry.visual` |
| Arm thickness | 4.0 mm | `corroborated` | S9, S10, S11 | 複数仕様で一致 | High | `geometry.visual` |
| Motor mounting hole spacing | 9x9 mm / 12x12 mm | `manufacturer` | S4 p.5 | Installation PDFに明記 | High | Interface Variant / motor mount metadata |
| Front motor wire recommended length | 76 mm | `manufacturer` | S4 p.5 | geometryそのものではないが、front/rearを区別する一次資料 | High | review evidence only |
| Rear motor wire recommended length | 62 mm | `manufacturer` | S4 p.5 | geometryそのものではないが、front/rearを区別する一次資料 | High | review evidence only |
| Camera installation pitch / width | 19 / 20 mm | `corroborated` | S9, S10, S11 | 複数仕様で一致 | High | Camera mount Interface candidate |
| Stack installation height | 11 mm | `corroborated` | S9, S10, S11 | 中央部のvertical envelope制約として使える | High | frame/electronics geometry constraint |
| Stack mounting holes | 25.5 x 25.5 mm | `corroborated` | S9, S10, S11 | 複数仕様で一致 | High | electronics mount Interface candidate |
| Frame weight without head | 87 +/- 2 g | `corroborated` | S9, S10, S11 | head variantとの質量境界を別途確認する必要あり | High | `mass_kg` scope check |
| Maximum supported battery envelope | 67 x 31 x 40 mm | `corroborated` | S10, S11 | 搭載可能領域。Frame自身の外形寸法ではない | High | battery compatibility metadata |
| GPS supported size | 18.1 x 18.1 mm | `corroborated` | S10, S11 | printed part交換条件あり | Medium-High | accessory compatibility |
| Compatible propeller size | 3.0-3.6 inch | `corroborated` | S9, S10, S11 | 複数仕様で一致 | High | compatibility metadata |
| Aluminum standoff nominal length | 11 mm | `manufacturer` | S4 p.2/p.6 | `M2x11mm Aluminum Standoff` と記載。どのplate間距離を直接拘束するかは図面解釈が必要 | High for part length / Medium for frame Z inference | geometry constraint |

## Manufacturer-confirmed structural boundaries

S4の組立資料では、少なくとも次の部品が明示的に分離されている。

| 構成 | Evidence | 出典 | Catalog責務 |
| --- | --- | --- | --- |
| Top plate | `manufacturer` | S4 p.2 | Frame |
| Middle plate | `manufacturer` | S4 p.2 | Frame |
| Bottom plate | `manufacturer` | S4 p.2 | Frame |
| Arm | `manufacturer` | S4 p.2 | Frame |
| Arm Pad | `manufacturer` | S4 p.2 | Frame / structural accessory |
| Injection Molded Front Support | `manufacturer` | S4 p.2, p.5 | Frame / Head variant |
| Injection Molded Side Plate | `manufacturer` | S4 p.2, p.7 | Frame |
| Receiver Cover | `manufacturer` | S4 p.2, p.7 | Frame / accessory |
| VTX Module | `manufacturer` | S4 p.2, p.9 | Electronics, not Camera |
| GPS Mount | `manufacturer` | S4 p.2/p.6 | Accessory |
| Battery Anti-slip Pad / Strap Fixing Piece | `manufacturer` | S4 p.2/p.6 | Frame accessory |
| AIO | `manufacturer` boundary | S4 p.4 | Frame packageに含まれない。Electronics |
| Receiver | `manufacturer` boundary | S4 p.7 | Frame packageに含まれない。Electronics |
| Motors / motor wires | `manufacturer` boundary | S4 p.5 | Frame packageに含まれない。Motor / wiring |

この境界は、PR #10で行った `Frame / Camera / Electronics` の責務分離を支持する。

## Current YAML values that are not yet evidence-confirmed

| YAML項目 | 現在値 | 現在の由来 | Evidence判定 | 問題 | 次に必要な資料 |
| --- | ---: | --- | --- | --- | --- |
| `dimensions_m` | `[0.171, 0.171, 0.021]` | simulation envelope | `estimated` | 171 mmはwheelbaseであり外形L/Wではない。21 mmもFrame variant全体の高さとして直接確定していない | 正投影寸法図、公式外形寸法、または実測 |
| motor X/Y center offsets | `+/- 60.46 mm` | `171/(2*sqrt(2))` | `derived` from unverified assumption | 数式は正しいが、正方形True-X仮定が未確認 | front/rearおよびleft/right motor-center distance、または各Motor center座標 |
| arm yaw | `+/-45 deg` | True-X assumption | `inferred` | 実機planform未確定 | Motor center rectangleまたはarm drawing |
| arm length / width | current primitive approximation | photo/reference approximation | `estimated` | thickness 4 mm以外のplanform寸法が未確定 | Arm単体寸法、正投影図、実測 |
| plate planform L/W | current primitive approximation | photo/reference approximation | `estimated` | 厚み以外の外形寸法が未確定 | plate drawing / measured asset |
| side plate L/H/pose | current primitive approximation | photo/reference approximation | `inferred` | 部品存在は一次確認済み、寸法未確定 | side plate寸法または実測 |
| front support dimensions / pose | current primitive approximation | photo/reference approximation | `inferred` | 部品存在は一次確認済み、寸法未確定 | official head/front support drawingまたは実測 |
| `camera_mount` pose | `[0.067, 0, 0.014]` | simulation estimate | `estimated` | 19/20 mmはmount幅であり、Frame座標系での軸位置を与えない | pivot/axis位置、head drawing |
| `battery_mount` pose | `[-0.008, 0, 0.016]` | simulation estimate | `estimated` | max battery envelopeは位置を決めない | mounting surface位置、strap位置、plate drawing |
| `electronics_mount` pose | `[0, 0, 0.0105]` | simulation estimate | `estimated` | stack hole/heightは制約になるがabsolute poseは未確定 | plate hole位置、stack seating plane |
| center of mass / inertia | current mass proxy | simulation proxy | `estimated` | 主要内部部品の質量・位置未反映 | AIO/VTX/Receiver/Batteryの質量・位置 |

## Conditional derivations: usable only with explicit assumptions

### True-X square assumption

現在のMotor center offsetは次式で作られている。

```text
wheelbase = 171 mm
x = y
sqrt((2x)^2 + (2y)^2) = 171
x = 171 / (2*sqrt(2)) = 60.4576 mm
```

この導出自体は正しい。しかし `x = y` は未確認であるため、実機寸法としては確定しない。

YAMLへ残す場合も、`derived_from_wheelbase_under_true_x_assumption` のように仮定を名前へ含める。一次資料でX/Yが得られた時点で置換する。

### Vertical stack constraint

`stack installation height = 11 mm`、plate thickness、`M2x11 mm` standoffはZ方向を絞る有力な制約である。ただし、各standoffがどのplate間に入り、どの面をheight基準にしているかを組立図から確認する前に、absolute Zへ直接変換しない。

## Rooted inference policy

一次資料で寸法が得られない場合のみ、以下の順で推定する。

1. 既知のmanufacturer寸法を基準にする。
2. 可能な限り正面・側面・上面に近い公式画像を使う。
3. 同一画像上で基準寸法と対象寸法のpixel比を測る。
4. 計算式を残す。
5. 透視歪み・画像解像度・部品の隠れを考慮した不確かさを付ける。
6. `inferred` として記録し、manufacturer / measured値で後から置換できるようにする。

例:

```text
target_mm = reference_mm * target_px / reference_px

source_image = <source id + image identifier>
reference = 25.5 mm stack-hole spacing
reference_px = ...
target = side-plate length
target_px = ...
result = ... mm
uncertainty = +/- ... mm
```

異なる透視面にある寸法同士を単純なpixel比で換算しない。

`estimated` を使う場合は、なぜ `manufacturer / measured / derived / inferred` にできなかったかを必ず書く。

## Geometry PR gate

次のMaster3X geometry変更PRでは、変更する値ごとにこの文書の行を引用し、Evidence分類を示す。

最低限、以下を優先的に埋める。

- [ ] front/rear Motor center distance
- [ ] left/right Motor center distance
- [ ] Arm planform length / width / root position / yaw
- [ ] Top / Middle / Bottom plate planform L/W
- [ ] Frame outer L/W/H by head variant
- [ ] Front Support / Head structural envelope and mounting pose
- [ ] Side Plate L/H and mounting pose
- [ ] Camera pivot axis position
- [ ] Stack seating plane and electronics absolute Z
- [ ] AIO / VTX / Receiver representative dimensions and masses for rigid-body proxies

全項目がmanufacturer値になる必要はない。`inferred` が残ってもよいが、**根拠・計算法・不確かさが説明できない推定値を減らすこと**を合格条件とする。

## Current conclusion

現時点では、厚み、mount規格、部品境界、stack制約等はかなり根拠が取れている。一方、Master3Xのplanformを決めるMotor center X/Y、各plateの平面外形、Front Support / Side Plateの実寸はまだ不足している。

したがって、次のgeometry修正で最も価値が高いのは「見た目を合わせて数値を動かす」ことではなく、これら未確定寸法の一次資料または根拠ある推定を先に埋めることである。
