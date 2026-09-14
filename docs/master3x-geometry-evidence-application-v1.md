# Master3X Geometry Evidence Application v1

## 目的

この文書は `docs/master3x-dimension-evidence.md` のEvidence Matrixを、今回の `speedybee_master3x` geometryへどう適用したかを記録する。

Evidence Matrixは「何が分かっているか」の正本であり、この文書は「その根拠を今回どう数値へ落としたか」の適用記録である。

不確定なplanform寸法を新たに確定値へ昇格させない。Motor center X/Y、arm yaw、plate L/W、camera pivot X/Zは今回変更しない。

## 適用した根拠

| 対象 | 適用値 | Evidence | 出典 | 適用方法 | Confidence / uncertainty |
| --- | ---: | --- | --- | --- | --- |
| Top / Middle / Bottom plate thickness | 2 mm | `corroborated` | Evidence Matrix S9-S11 | 既存2 mmを維持 | High |
| Arm thickness | 4 mm | `corroborated` | Evidence Matrix S9-S11 | 既存4 mmを維持 | High |
| Aluminum standoff length | 11 mm | `manufacturer` | S4 p.2, p.3, p.6 | visual standoff cylinderを12 mmから11 mmへ変更 | High for part length |
| Stack installation height | 11 mm | `corroborated` + assembly-rooted inference | S4 p.4, p.7-p.8 + S9-S11 | AIOはMiddle Plateへ固定され、Side Plateを介してTop Plateが上に載る組立順序から、Middle Plate上面→Top Plate下面の内部クリアランスとして適用 | Medium-High; manufacturer text does not explicitly define the two datum surfaces |
| Camera installation width | 19 / 20 mm | `corroborated` | S9-S11 | 20 mm互換を優先し、左右front-support primitiveの内側間隔を20 mmへ制約 | Medium; support wall thickness/shape remains inferred |
| Electronics mounting plane | Middle Plate upper surface | `manufacturer` structure + derived | S4 p.4 | AIO installation is explicitly on the Middle Plate; `electronics_mount` ZをMiddle Plate上面へ置く | High for owning plate / Medium for local origin convention |
| Battery mounting plane | upper carbon plate / pad surface | `manufacturer` structure + derived | S4 p.6 | battery strap fixing piece is placed on the upper carbon plate; `battery_mount` ZをTop Plate + pad proxy上面へ追従 | High for owning plate / Medium for pad proxy thickness |

## Vertical stack derivation

現在のMiddle Plate center Zは `6.5 mm`、plate thicknessは `2 mm` なので、上面は:

```text
middle_top = 6.5 + 1.0 = 7.5 mm
```

11 mmのstack installation heightを内部クリアランスとして適用すると:

```text
top_bottom = 7.5 + 11.0 = 18.5 mm
top_center = 18.5 + 1.0 = 19.5 mm
```

したがって今回のTop Plate center Zは `19.5 mm` とする。

この解釈は、S4でAIOがMiddle Plateへ取り付けられ、Side Plateの上にTop Plateを載せる組立順序と整合する。ただしメーカー資料が「stack installation height」の基準面を文章で明示しているわけではないため、分類は `manufacturer` ではなく **assembly-rooted inference** とする。

## Side structure derivation

Middle Plate上面 `7.5 mm` からTop Plate下面 `18.5 mm` までを中央stack bayとみなし、Side Plate / brace proxyのZ spanを11 mmとする。

```text
side_center_z = (7.5 + 18.5) / 2 = 13.0 mm
side_height = 11.0 mm
```

Side Plateのplanform length、Y位置、brace角度は依然として `inferred / estimated` であり、今回確定しない。

## Front support / camera opening derivation

対応camera installation widthは `19 / 20 mm`。今回のgeneric demo cameraは特定製品ではないため、互換上限の20 mmをopening constraintとして使う。

front-support side primitiveの厚みは既存の3 mm proxyを維持し、inner openingを20 mmにするため:

```text
inner_half_width = 10.0 mm
wall_half_thickness = 1.5 mm
support_center_y = 10.0 + 1.5 = 11.5 mm
```

したがって左右support centerを `y = +/-11.5 mm` とする。外側spanは26 mmになる。

重要: これは**実際のInjection Molded Front Supportの外寸を20/26 mmと断定するものではない**。確認済みのcamera互換幅を、現在のprimitive approximationへ制約として適用した rooted inference である。

## 今回変更しない値

以下はEvidence Matrix上まだ根拠不足なので変更しない。

- Motor center offsets `+/-60.46 mm`
- arm yaw `+/-45 deg`
- arm planform length / width / root position
- Top / Middle / Bottom plate planform L/W
- side plate planform length / Y pose
- camera mount X/Z and pivot axis
- Frame outer `dimensions_m`
- inertial proxy / center of mass

これらは一次寸法、計測、またはEvidence MatrixのRooted inference policyに従った計測結果が得られた時点で次のgeometry revisionで更新する。

## 受入条件

- 11 mm standoffがCatalog geometryに反映されている。
- Middle Plate上面→Top Plate下面が11 mmである。
- front support inner openingが20 mmである。
- `electronics_mount` がMiddle Plate上面にある。
- `battery_mount` がTop Plate / pad proxy上面に追従している。
- Motor center positionsとInterface Variantは変更されていない。
- 変更していないplanform推定値をmanufacturer値として表現していない。
