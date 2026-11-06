# Relatório de interpenetração de membros (FEAT-001)

Evidência numérica gerada por `tools/detectar_colisao.py` sobre as poses reais do companion. Profundidades em unidades do modelo (`u`), a mesma escala de `comprimento_u` em `rig_medidas`.

- Poses varridas: **29** (instantes por pose: 0.00s, 0.30s, 0.60s, 1.00s, 1.50s, 2.00s, 2.60s).
- Limiar de colisão: **0.020 u**.
- Pares verificados: **22** (lista curada, não todos-contra-todos).

## Interpenetração por par/pose

| Pose | Par | Prof. máx (u) | Prof. média (u) | t do pico (s) |
| --- | --- | ---: | ---: | ---: |
| interaction:wake | braço dir. vs tronco | 0.458 | 0.455 | 0.30 |
| interaction:wake | braço esq. vs tronco | 0.458 | 0.455 | 0.30 |
| idle:confident | braço esq. vs tronco | 0.458 | 0.456 | 2.60 |
| interaction:hover | braço esq. vs tronco | 0.457 | 0.457 | 0.00 |
| flourish:stretch | braço esq. vs tronco | 0.457 | 0.453 | 0.30 |
| interaction:pet | braço esq. vs tronco | 0.457 | 0.455 | 0.30 |
| flourish:wave | braço dir. vs tronco | 0.457 | 0.456 | 0.30 |
| idle:calm | braço esq. vs tronco | 0.456 | 0.453 | 0.00 |
| idle:street | braço dir. vs tronco | 0.456 | 0.449 | 0.00 |
| idle:rhythm | braço esq. vs tronco | 0.456 | 0.450 | 0.60 |
| idle:curious | braço dir. vs tronco | 0.455 | 0.453 | 0.00 |
| interaction:double_click | braço esq. vs tronco | 0.455 | 0.454 | 0.30 |
| idle:playful | braço esq. vs tronco | 0.455 | 0.450 | 0.00 |
| dance | braço esq. vs tronco | 0.455 | 0.443 | 0.00 |
| flourish:wave | braço esq. vs tronco | 0.455 | 0.450 | 0.00 |
| flourish:peek | braço esq. vs tronco | 0.455 | 0.455 | 0.00 |
| interaction:click | braço esq. vs tronco | 0.455 | 0.455 | 0.00 |
| interaction:poke | braço esq. vs tronco | 0.455 | 0.452 | 0.00 |
| interaction:land | braço esq. vs tronco | 0.455 | 0.450 | 0.00 |
| idle:playful | braço dir. vs tronco | 0.455 | 0.450 | 0.00 |
| idle:rhythm | braço dir. vs tronco | 0.455 | 0.449 | 0.00 |
| dance | braço dir. vs tronco | 0.455 | 0.443 | 0.00 |
| flourish:stretch | braço dir. vs tronco | 0.455 | 0.452 | 0.00 |
| flourish:peek | braço dir. vs tronco | 0.455 | 0.455 | 0.00 |
| interaction:hover | braço dir. vs tronco | 0.455 | 0.455 | 0.00 |
| interaction:click | braço dir. vs tronco | 0.455 | 0.455 | 0.00 |
| interaction:double_click | braço dir. vs tronco | 0.455 | 0.454 | 0.00 |
| interaction:pet | braço dir. vs tronco | 0.455 | 0.451 | 0.00 |
| interaction:poke | braço dir. vs tronco | 0.455 | 0.453 | 0.00 |
| interaction:land | braço dir. vs tronco | 0.455 | 0.450 | 0.00 |
| idle:fighter | braço esq. vs tronco | 0.455 | 0.427 | 2.60 |
| idle:calm | braço dir. vs tronco | 0.454 | 0.453 | 0.60 |
| idle:confident | braço dir. vs tronco | 0.454 | 0.453 | 0.60 |
| idle:fighter | braço dir. vs tronco | 0.454 | 0.452 | 0.00 |
| drag | braço dir. vs tronco | 0.453 | 0.453 | 0.00 |
| drag | braço esq. vs tronco | 0.453 | 0.453 | 0.00 |
| walk | braço dir. vs tronco | 0.453 | 0.452 | 0.00 |
| walk | braço esq. vs tronco | 0.453 | 0.453 | 0.00 |
| sleep | braço dir. vs tronco | 0.453 | 0.452 | 0.00 |
| idle:stylish | braço dir. vs tronco | 0.453 | 0.450 | 2.00 |
| idle:curious | braço esq. vs tronco | 0.451 | 0.450 | 1.50 |
| dance:head_bob | braço esq. vs tronco | 0.450 | 0.450 | 0.00 |
| dance:hip_hop | braço esq. vs tronco | 0.450 | 0.450 | 0.00 |
| dance:rock | braço esq. vs tronco | 0.450 | 0.450 | 0.00 |
| dance:breakdance | braço esq. vs tronco | 0.450 | 0.450 | 0.00 |
| idle:shy | braço esq. vs tronco | 0.449 | 0.449 | 0.00 |
| idle:street | braço esq. vs tronco | 0.449 | 0.444 | 1.00 |
| idle:shy | braço dir. vs tronco | 0.448 | 0.448 | 0.30 |
| idle:stylish | braço esq. vs tronco | 0.447 | 0.442 | 0.00 |
| sleep | braço esq. vs tronco | 0.446 | 0.446 | 2.00 |
| run | braço dir. vs tronco | 0.443 | 0.443 | 0.00 |
| run | braço esq. vs tronco | 0.443 | 0.441 | 0.00 |
| fall | braço esq. vs tronco | 0.442 | 0.441 | 1.50 |
| dance:head_bob | braço dir. vs tronco | 0.434 | 0.434 | 0.00 |
| dance:hip_hop | braço dir. vs tronco | 0.434 | 0.434 | 0.00 |
| dance:rock | braço dir. vs tronco | 0.434 | 0.434 | 0.00 |
| dance:breakdance | braço dir. vs tronco | 0.434 | 0.434 | 0.00 |
| fall | braço dir. vs tronco | 0.433 | 0.433 | 0.00 |
| interaction:wake | antebraço esq. vs tronco | 0.414 | 0.326 | 0.60 |
| interaction:wake | antebraço dir. vs tronco | 0.414 | 0.327 | 0.60 |
| flourish:wave | antebraço dir. vs tronco | 0.395 | 0.335 | 1.00 |
| idle:curious | antebraço dir. vs tronco | 0.372 | 0.322 | 0.00 |
| idle:fighter | antebraço dir. vs tronco | 0.359 | 0.322 | 2.00 |
| idle:stylish | antebraço dir. vs tronco | 0.355 | 0.324 | 2.00 |
| fall | antebraço esq. vs tronco | 0.337 | 0.333 | 1.50 |
| idle:street | antebraço dir. vs tronco | 0.332 | 0.310 | 2.00 |
| dance | antebraço dir. vs tronco | 0.331 | 0.300 | 1.00 |
| dance | antebraço esq. vs tronco | 0.331 | 0.304 | 0.30 |
| interaction:poke | antebraço dir. vs tronco | 0.327 | 0.304 | 0.30 |
| dance:head_bob | antebraço esq. vs tronco | 0.325 | 0.325 | 0.00 |
| dance:hip_hop | antebraço esq. vs tronco | 0.325 | 0.325 | 0.00 |
| dance:rock | antebraço esq. vs tronco | 0.325 | 0.325 | 0.00 |
| dance:breakdance | antebraço esq. vs tronco | 0.325 | 0.325 | 0.00 |
| interaction:wake | braço dir. vs braço esq. | 0.320 | 0.112 | 0.60 |
| run | antebraço dir. vs tronco | 0.318 | 0.305 | 0.30 |
| flourish:stretch | antebraço esq. vs tronco | 0.313 | 0.301 | 1.50 |
| flourish:stretch | antebraço dir. vs tronco | 0.311 | 0.301 | 1.00 |
| interaction:pet | antebraço esq. vs tronco | 0.311 | 0.304 | 0.60 |
| idle:playful | antebraço esq. vs tronco | 0.310 | 0.305 | 1.50 |
| idle:rhythm | antebraço esq. vs tronco | 0.309 | 0.301 | 0.60 |
| sleep | antebraço dir. vs tronco | 0.309 | 0.309 | 0.00 |
| walk | antebraço esq. vs tronco | 0.309 | 0.301 | 1.50 |
| idle:street | antebraço esq. vs tronco | 0.308 | 0.293 | 2.60 |
| idle:rhythm | antebraço dir. vs tronco | 0.308 | 0.300 | 2.00 |
| idle:shy | antebraço dir. vs tronco | 0.307 | 0.307 | 0.00 |
| fall | antebraço dir. vs tronco | 0.307 | 0.299 | 1.50 |
| idle:calm | antebraço esq. vs tronco | 0.304 | 0.302 | 2.60 |
| idle:curious | antebraço esq. vs tronco | 0.304 | 0.302 | 2.60 |
| idle:confident | antebraço esq. vs tronco | 0.304 | 0.302 | 2.60 |
| walk | antebraço dir. vs tronco | 0.303 | 0.299 | 0.60 |
| drag | antebraço dir. vs tronco | 0.300 | 0.300 | 0.00 |
| drag | antebraço esq. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:double_click | antebraço dir. vs tronco | 0.300 | 0.300 | 0.30 |
| interaction:double_click | antebraço esq. vs tronco | 0.300 | 0.300 | 0.30 |
| idle:playful | antebraço dir. vs tronco | 0.300 | 0.295 | 0.00 |
| idle:confident | antebraço dir. vs tronco | 0.300 | 0.298 | 0.00 |
| flourish:peek | antebraço dir. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:hover | antebraço dir. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:click | antebraço dir. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:pet | antebraço dir. vs tronco | 0.300 | 0.296 | 0.00 |
| interaction:land | antebraço dir. vs tronco | 0.300 | 0.300 | 0.00 |
| run | antebraço esq. vs tronco | 0.300 | 0.295 | 0.00 |
| flourish:wave | antebraço esq. vs tronco | 0.300 | 0.295 | 0.00 |
| flourish:peek | antebraço esq. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:hover | antebraço esq. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:click | antebraço esq. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:poke | antebraço esq. vs tronco | 0.300 | 0.300 | 0.00 |
| interaction:land | antebraço esq. vs tronco | 0.300 | 0.300 | 0.00 |
| idle:fighter | antebraço esq. vs tronco | 0.300 | 0.293 | 2.60 |
| idle:calm | antebraço dir. vs tronco | 0.299 | 0.298 | 0.60 |
| idle:shy | antebraço esq. vs tronco | 0.294 | 0.294 | 0.00 |
| idle:stylish | antebraço esq. vs tronco | 0.292 | 0.287 | 0.00 |
| sleep | antebraço esq. vs tronco | 0.291 | 0.291 | 2.00 |
| dance:head_bob | antebraço dir. vs tronco | 0.282 | 0.282 | 0.00 |
| dance:hip_hop | antebraço dir. vs tronco | 0.282 | 0.282 | 0.00 |
| dance:rock | antebraço dir. vs tronco | 0.282 | 0.282 | 0.00 |
| dance:breakdance | antebraço dir. vs tronco | 0.282 | 0.282 | 0.00 |
| interaction:wake | antebraço dir. vs cabeça | 0.282 | 0.205 | 0.60 |
| interaction:wake | antebraço esq. vs cabeça | 0.279 | 0.203 | 0.60 |
| flourish:wave | antebraço dir. vs cabeça | 0.268 | 0.212 | 1.00 |
| idle:stylish | antebraço dir. vs cabeça | 0.259 | 0.206 | 2.60 |
| idle:curious | antebraço dir. vs cabeça | 0.249 | 0.210 | 0.00 |
| idle:street | antebraço dir. vs cabeça | 0.244 | 0.191 | 2.00 |
| idle:fighter | antebraço dir. vs cabeça | 0.234 | 0.197 | 2.00 |
| interaction:poke | antebraço dir. vs cabeça | 0.221 | 0.186 | 0.30 |
| idle:fighter | mão dir. vs tronco | 0.220 | 0.152 | 2.00 |
| idle:stylish | mão dir. vs tronco | 0.215 | 0.157 | 2.60 |
| fall | antebraço esq. vs cabeça | 0.214 | 0.214 | 1.50 |
| interaction:wake | mão dir. vs tronco | 0.213 | 0.144 | 0.60 |
| interaction:wake | mão esq. vs tronco | 0.211 | 0.143 | 0.60 |
| interaction:click | antebraço dir. vs cabeça | 0.203 | 0.194 | 0.30 |
| interaction:hover | braço dir. vs braço esq. | 0.201 | 0.201 | 0.00 |
| interaction:pet | antebraço dir. vs cabeça | 0.198 | 0.191 | 0.60 |
| interaction:hover | antebraço dir. vs cabeça | 0.198 | 0.198 | 0.00 |
| dance | pernas vs pé dir. | 0.195 | 0.194 | 1.50 |
| fall | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| dance | pernas vs pé esq. | 0.195 | 0.194 | 0.30 |
| dance:head_bob | antebraço dir. vs cabeça | 0.195 | 0.189 | 0.30 |
| dance:hip_hop | antebraço dir. vs cabeça | 0.195 | 0.189 | 0.30 |
| dance:rock | antebraço dir. vs cabeça | 0.195 | 0.189 | 0.30 |
| dance:breakdance | antebraço dir. vs cabeça | 0.195 | 0.189 | 0.30 |
| idle:calm | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:calm | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:curious | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:curious | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:playful | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:playful | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:shy | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:shy | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:confident | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:confident | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:street | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:street | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:fighter | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:fighter | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:rhythm | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:rhythm | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| idle:stylish | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| idle:stylish | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| walk | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| walk | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| run | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| run | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| drag | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| drag | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| fall | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| dance:head_bob | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| dance:head_bob | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| dance:hip_hop | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| dance:hip_hop | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| dance:rock | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| dance:rock | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| dance:breakdance | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| dance:breakdance | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| sleep | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| sleep | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| flourish:wave | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| flourish:wave | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| flourish:stretch | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| flourish:stretch | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| flourish:peek | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| flourish:peek | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| interaction:hover | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| interaction:hover | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| interaction:click | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| interaction:click | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| interaction:double_click | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| interaction:double_click | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| interaction:pet | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| interaction:pet | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| interaction:poke | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| interaction:poke | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| interaction:land | pernas vs pé esq. | 0.195 | 0.194 | 0.00 |
| interaction:land | pernas vs pé dir. | 0.195 | 0.194 | 0.00 |
| interaction:wake | pernas vs pé esq. | 0.195 | 0.195 | 0.00 |
| interaction:wake | pernas vs pé dir. | 0.195 | 0.195 | 0.00 |
| interaction:hover | antebraço esq. vs cabeça | 0.194 | 0.194 | 0.00 |
| interaction:click | antebraço esq. vs cabeça | 0.191 | 0.190 | 0.00 |
| idle:curious | mão dir. vs tronco | 0.190 | 0.145 | 0.00 |
| idle:rhythm | antebraço dir. vs cabeça | 0.189 | 0.181 | 2.60 |
| dance | antebraço esq. vs cabeça | 0.189 | 0.183 | 2.60 |
| flourish:peek | antebraço dir. vs cabeça | 0.187 | 0.183 | 2.60 |
| dance | antebraço dir. vs cabeça | 0.187 | 0.181 | 0.30 |
| idle:shy | antebraço esq. vs cabeça | 0.186 | 0.186 | 0.00 |
| idle:fighter | antebraço esq. vs cabeça | 0.186 | 0.181 | 2.00 |
| interaction:pet | antebraço esq. vs cabeça | 0.185 | 0.184 | 0.00 |
| idle:playful | antebraço dir. vs cabeça | 0.185 | 0.183 | 1.50 |
| dance:head_bob | antebraço esq. vs cabeça | 0.184 | 0.183 | 1.50 |
| dance:hip_hop | antebraço esq. vs cabeça | 0.184 | 0.183 | 1.50 |
| dance:rock | antebraço esq. vs cabeça | 0.184 | 0.183 | 1.50 |
| dance:breakdance | antebraço esq. vs cabeça | 0.184 | 0.183 | 1.50 |
| interaction:double_click | antebraço dir. vs cabeça | 0.183 | 0.183 | 0.60 |
| interaction:double_click | antebraço esq. vs cabeça | 0.182 | 0.182 | 1.00 |
| idle:curious | antebraço esq. vs cabeça | 0.182 | 0.181 | 2.60 |
| idle:confident | antebraço dir. vs cabeça | 0.182 | 0.181 | 2.60 |
| fall | antebraço dir. vs cabeça | 0.182 | 0.180 | 1.50 |
| flourish:stretch | antebraço esq. vs cabeça | 0.182 | 0.181 | 1.50 |
| idle:calm | antebraço esq. vs cabeça | 0.181 | 0.180 | 0.00 |
| flourish:stretch | antebraço dir. vs cabeça | 0.181 | 0.180 | 2.00 |
| sleep | antebraço dir. vs cabeça | 0.181 | 0.181 | 0.00 |
| idle:street | antebraço esq. vs cabeça | 0.181 | 0.179 | 2.60 |
| run | antebraço dir. vs cabeça | 0.181 | 0.180 | 0.30 |
| walk | antebraço esq. vs cabeça | 0.181 | 0.180 | 1.50 |
| drag | antebraço dir. vs cabeça | 0.180 | 0.180 | 0.00 |
| sleep | antebraço esq. vs cabeça | 0.180 | 0.180 | 0.00 |
| idle:calm | antebraço dir. vs cabeça | 0.180 | 0.180 | 2.60 |
| walk | antebraço dir. vs cabeça | 0.180 | 0.180 | 1.50 |
| run | antebraço esq. vs cabeça | 0.180 | 0.180 | 0.30 |
| idle:playful | antebraço esq. vs cabeça | 0.180 | 0.179 | 2.60 |
| drag | antebraço esq. vs cabeça | 0.180 | 0.180 | 0.00 |
| interaction:land | antebraço dir. vs cabeça | 0.180 | 0.180 | 0.00 |
| idle:confident | antebraço esq. vs cabeça | 0.180 | 0.179 | 0.00 |
| idle:rhythm | antebraço esq. vs cabeça | 0.180 | 0.180 | 0.00 |
| flourish:wave | antebraço esq. vs cabeça | 0.180 | 0.179 | 0.00 |
| flourish:peek | antebraço esq. vs cabeça | 0.180 | 0.179 | 0.00 |
| interaction:poke | antebraço esq. vs cabeça | 0.180 | 0.179 | 0.00 |
| interaction:land | antebraço esq. vs cabeça | 0.180 | 0.180 | 0.00 |
| fall | mão esq. vs tronco | 0.180 | 0.175 | 0.60 |
| idle:stylish | antebraço esq. vs cabeça | 0.180 | 0.178 | 2.00 |
| idle:shy | antebraço dir. vs cabeça | 0.177 | 0.176 | 2.60 |
| dance | mão dir. vs tronco | 0.156 | 0.125 | 1.00 |
| dance | mão esq. vs tronco | 0.156 | 0.129 | 0.30 |
| dance:head_bob | mão esq. vs tronco | 0.151 | 0.151 | 0.00 |
| dance:hip_hop | mão esq. vs tronco | 0.151 | 0.151 | 0.00 |
| dance:rock | mão esq. vs tronco | 0.151 | 0.151 | 0.00 |
| dance:breakdance | mão esq. vs tronco | 0.151 | 0.151 | 0.00 |
| flourish:stretch | mão esq. vs tronco | 0.149 | 0.127 | 1.50 |
| flourish:stretch | mão dir. vs tronco | 0.148 | 0.127 | 1.00 |
| idle:street | mão dir. vs tronco | 0.146 | 0.133 | 2.00 |
| interaction:poke | mão dir. vs tronco | 0.144 | 0.127 | 0.30 |
| run | mão dir. vs tronco | 0.142 | 0.129 | 0.30 |
| flourish:wave | mão dir. vs tronco | 0.138 | 0.129 | 0.60 |
| interaction:pet | mão esq. vs tronco | 0.134 | 0.128 | 0.60 |
| idle:playful | mão esq. vs tronco | 0.134 | 0.129 | 1.50 |
| idle:street | mão esq. vs tronco | 0.133 | 0.117 | 2.60 |
| idle:rhythm | mão esq. vs tronco | 0.133 | 0.125 | 0.60 |
| sleep | mão dir. vs tronco | 0.133 | 0.133 | 0.00 |
| walk | mão esq. vs tronco | 0.133 | 0.124 | 1.50 |
| idle:rhythm | mão dir. vs tronco | 0.131 | 0.122 | 2.00 |
| idle:shy | mão dir. vs tronco | 0.131 | 0.131 | 0.00 |
| fall | mão dir. vs tronco | 0.131 | 0.122 | 1.50 |
| interaction:click | antebraço esq. vs portinha | 0.129 | 0.090 | 0.30 |
| idle:calm | mão esq. vs tronco | 0.128 | 0.126 | 2.60 |
| idle:curious | mão esq. vs tronco | 0.128 | 0.126 | 2.60 |
| idle:confident | mão esq. vs tronco | 0.128 | 0.125 | 2.60 |
| walk | mão dir. vs tronco | 0.127 | 0.123 | 0.60 |
| dance | antebraço esq. vs portinha | 0.126 | 0.080 | 0.30 |
| flourish:peek | antebraço esq. vs portinha | 0.126 | 0.077 | 1.50 |
| idle:stylish | mão dir. vs cabeça | 0.124 | 0.088 | 2.60 |
| drag | mão dir. vs tronco | 0.124 | 0.124 | 0.00 |
| drag | mão esq. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:double_click | mão dir. vs tronco | 0.124 | 0.124 | 0.30 |
| interaction:double_click | mão esq. vs tronco | 0.124 | 0.124 | 0.30 |
| idle:fighter | mão esq. vs tronco | 0.124 | 0.118 | 2.60 |
| idle:playful | mão dir. vs tronco | 0.124 | 0.119 | 0.00 |
| idle:confident | mão dir. vs tronco | 0.124 | 0.122 | 0.00 |
| flourish:peek | mão dir. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:hover | mão dir. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:click | mão dir. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:pet | mão dir. vs tronco | 0.124 | 0.120 | 0.00 |
| interaction:land | mão dir. vs tronco | 0.124 | 0.124 | 0.00 |
| run | mão esq. vs tronco | 0.124 | 0.119 | 0.00 |
| flourish:wave | mão esq. vs tronco | 0.124 | 0.119 | 0.00 |
| flourish:peek | mão esq. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:hover | mão esq. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:click | mão esq. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:poke | mão esq. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:land | mão esq. vs tronco | 0.124 | 0.124 | 0.00 |
| interaction:pet | antebraço esq. vs portinha | 0.123 | 0.081 | 0.60 |
| idle:calm | mão dir. vs tronco | 0.123 | 0.121 | 0.60 |
| idle:shy | mão esq. vs tronco | 0.118 | 0.118 | 0.00 |
| idle:stylish | mão esq. vs tronco | 0.116 | 0.112 | 0.00 |
| sleep | mão esq. vs tronco | 0.115 | 0.115 | 2.00 |
| interaction:poke | antebraço esq. vs portinha | 0.113 | 0.034 | 0.30 |
| interaction:hover | antebraço esq. vs portinha | 0.108 | 0.108 | 0.00 |
| dance:head_bob | mão dir. vs tronco | 0.108 | 0.108 | 0.00 |
| dance:hip_hop | mão dir. vs tronco | 0.108 | 0.108 | 0.00 |
| dance:rock | mão dir. vs tronco | 0.108 | 0.108 | 0.00 |
| dance:breakdance | mão dir. vs tronco | 0.108 | 0.108 | 0.00 |
| interaction:wake | antebraço esq. vs portinha | 0.107 | 0.052 | 1.00 |
| interaction:wake | mão dir. vs cabeça | 0.095 | 0.072 | 0.60 |
| interaction:wake | mão esq. vs cabeça | 0.091 | 0.069 | 0.60 |
| idle:curious | mão dir. vs cabeça | 0.091 | 0.063 | 0.00 |
| dance:head_bob | antebraço esq. vs portinha | 0.087 | 0.078 | 0.30 |
| dance:hip_hop | antebraço esq. vs portinha | 0.087 | 0.078 | 0.30 |
| dance:rock | antebraço esq. vs portinha | 0.087 | 0.078 | 0.30 |
| dance:breakdance | antebraço esq. vs portinha | 0.087 | 0.078 | 0.30 |
| idle:stylish | antebraço esq. vs portinha | 0.085 | 0.046 | 2.00 |
| idle:curious | antebraço esq. vs portinha | 0.082 | 0.065 | 0.00 |
| flourish:wave | braço dir. vs braço esq. | 0.074 | 0.071 | 0.60 |
| idle:calm | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:curious | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:playful | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:shy | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:confident | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:street | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:fighter | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:rhythm | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| idle:stylish | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| walk | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| run | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| drag | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| fall | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| dance | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| dance:head_bob | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| dance:hip_hop | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| dance:rock | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| dance:breakdance | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| sleep | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| flourish:stretch | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| flourish:peek | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| interaction:click | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| interaction:double_click | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| interaction:pet | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| interaction:poke | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| interaction:land | braço dir. vs braço esq. | 0.070 | 0.070 | 0.00 |
| fall | mão esq. vs cabeça | 0.060 | 0.055 | 0.60 |
| idle:street | antebraço esq. vs portinha | 0.060 | 0.031 | 2.00 |
| idle:street | mão dir. vs cabeça | 0.054 | 0.054 | 2.00 |
| interaction:double_click | antebraço esq. vs portinha | 0.048 | 0.041 | 0.60 |
| idle:playful | antebraço esq. vs portinha | 0.043 | 0.034 | 1.50 |
| idle:confident | antebraço esq. vs portinha | 0.043 | 0.039 | 2.60 |
| interaction:poke | mão dir. vs cabeça | 0.043 | 0.043 | 0.30 |
| idle:fighter | mão dir. vs cabeça | 0.042 | 0.041 | 2.60 |
| interaction:wake | mão esq. vs portinha | 0.039 | 0.039 | 1.00 |
| dance | mão esq. vs portinha | 0.039 | 0.038 | 2.00 |
| interaction:click | mão dir. vs cabeça | 0.035 | 0.025 | 0.30 |
| dance:head_bob | mão esq. vs portinha | 0.033 | 0.030 | 1.50 |
| dance:hip_hop | mão esq. vs portinha | 0.033 | 0.030 | 1.50 |
| dance:rock | mão esq. vs portinha | 0.033 | 0.030 | 1.50 |
| dance:breakdance | mão esq. vs portinha | 0.033 | 0.030 | 1.50 |
| flourish:wave | antebraço esq. vs portinha | 0.033 | 0.026 | 0.60 |
| interaction:click | mão esq. vs portinha | 0.031 | 0.031 | 0.00 |
| interaction:hover | mão esq. vs portinha | 0.031 | 0.031 | 0.00 |
| interaction:hover | mão dir. vs cabeça | 0.031 | 0.031 | 0.00 |
| idle:fighter | antebraço esq. vs portinha | 0.030 | 0.030 | 2.60 |
| interaction:pet | mão dir. vs cabeça | 0.028 | 0.025 | 0.60 |
| interaction:pet | mão esq. vs portinha | 0.027 | 0.027 | 1.50 |
| interaction:hover | mão esq. vs cabeça | 0.027 | 0.027 | 0.00 |
| drag | antebraço esq. vs portinha | 0.027 | 0.027 | 0.00 |
| flourish:peek | mão esq. vs portinha | 0.027 | 0.024 | 0.60 |
| interaction:land | antebraço esq. vs portinha | 0.026 | 0.021 | 0.30 |
| flourish:stretch | antebraço esq. vs portinha | 0.026 | 0.022 | 0.30 |
| idle:calm | antebraço esq. vs portinha | 0.025 | 0.022 | 2.60 |
| idle:curious | mão esq. vs portinha | 0.024 | 0.023 | 0.00 |
| idle:rhythm | antebraço esq. vs portinha | 0.024 | 0.024 | 0.00 |
| dance:head_bob | mão dir. vs cabeça | 0.023 | 0.023 | 0.30 |
| dance:hip_hop | mão dir. vs cabeça | 0.023 | 0.023 | 0.30 |
| dance:rock | mão dir. vs cabeça | 0.023 | 0.023 | 0.30 |
| dance:breakdance | mão dir. vs cabeça | 0.023 | 0.023 | 0.30 |
| walk | antebraço esq. vs portinha | 0.023 | 0.021 | 0.60 |
| interaction:double_click | mão esq. vs portinha | 0.023 | 0.022 | 0.60 |
| interaction:click | mão esq. vs cabeça | 0.022 | 0.022 | 0.00 |
| interaction:poke | mão esq. vs portinha | 0.021 | 0.021 | 0.30 |

**Pior caso:** braço dir. vs tronco na pose `interaction:wake` — 0.458 u de penetração em t=0.30s.

### Como ler os números (overlap estrutural vs pose)

Dois sinais convivem na tabela e o FEAT-002 precisa separá-los:

- **Overlap ESTRUTURAL (constante em todas as poses):** `braço vs tronco` fica em ~0,45 u e `pernas vs pé` em exatamente 0,195 u em TODA pose, inclusive no repouso. Isso não é a pose atravessando o corpo: é a RAIZ do membro nascendo dentro do volume-bloco (o ombro/braço começa dentro da caixa do tronco; as pernas encostam nas caixas dos pés). É contato esperado pela montagem dos volumes, não defeito de animação.
- **Penetração dirigida pela POSE (varia com pose/instante):** os pares que mudam de profundidade conforme o gesto — `antebraço vs tronco` (até ~0,41 u no `wake`/`wave`), `antebraço vs cabeça` (até ~0,28 u), `mão vs tronco`, `braço dir. vs braço esq.` (0,07 u em repouso subindo a 0,32 u no `wake`) e `antebraço/mão vs portinha` — são os que realmente revelam o braço cruzando o corpo/cabeça. São esses que a correção deve mirar.

Recomendação de calibração para o FEAT-002: descontar o piso estrutural por par (subtrair a profundidade medida no repouso) OU encolher a cápsula do membro perto da raiz / afundar menos a origem na caixa, de modo que só o excedente dirigido pela pose conte como colisão a corrigir.

## Parâmetros calibráveis

Todos em `src/sejoga/colisao_membros.py`, no bloco `PARÂMETROS` do topo:

- `RAIOS_MEMBRO` e `RAIO_MEMBRO_PADRAO`: raio da cápsula por membro.
- `MEIA_DIM_TRONCO`, `MEIA_DIM_CABECA`, `MEIA_DIM_PORTA`: meias-dimensões das caixas orientadas.
- `AMOSTRAS_CAPSULA_CAIXA`: densidade da amostragem cápsula-vs-caixa.
- `LIMIAR_PENETRACAO_U`: profundidade mínima para contar como colisão.
- `PARES_A_CHECAR`: pares plausíveis varridos.

Valores atuais:

- raio `right-arm` = 0.160 u
- raio `left-arm` = 0.160 u
- raio `shoulder` = 0.160 u
- raio `shoulder2` = 0.160 u
- raio `ant-arm` = 0.130 u
- raio `ant-arm2` = 0.130 u
- raio `hand` = 0.110 u
- raio `hand2` = 0.110 u
- raio `fingers` = 0.090 u
- raio `fingers2` = 0.090 u
- raio `legs` = 0.200 u
- raio `left-feet` = 0.120 u
- raio `right-feet` = 0.120 u
- `MEIA_DIM_TRONCO` = (0.42, 0.55, 0.3)
- `MEIA_DIM_CABECA` = (0.3, 0.3, 0.3)
- `MEIA_DIM_PORTA` = (0.24, 0.24, 0.05)
- `LIMIAR_PENETRACAO_U` = 0.020 u

## Decisão para a correção (FEAT-002)

**Decisão: NÃO ligar a correção ao vivo no `AnimationController`. Entregar o gancho `resolver_colisoes` documentado e inerte.** A decisão é guiada pelos números acima, não assumida.

### Por que (a leitura dos números)

O detector mede a profundidade **bruta** de penetração e, como a própria tabela mostra, nessa profundidade convivem dois sinais que precisam ser separados antes de decidir corrigir:

1. **Piso estrutural (constante em TODA pose, inclusive repouso):** `braço vs tronco` fica em ~0,45 u e `pernas vs pé` em exatamente **0,195 u** em todas as 29 poses, sem variar com o gesto. Não é a animação atravessando o corpo: é a **raiz do membro nascendo dentro do volume-bloco** (ombro/braço começa dentro da caixa do tronco; a perna encosta na caixa do pé). É consequência da montagem dos volumes, não defeito de animação.
2. **Excedente dirigido pela pose (o único candidato real a correção):** descontando o piso por par (recomendação da seção *Como ler os números*), o que sobra é modesto:
   - `braço dir. vs braço esq.`: piso de repouso **0,070 u**, pico **0,320 u** em `interaction:wake` t=0.60 → excedente real ~**0,25 u** (recorrente em `wake`/`hover`);
   - `antebraço vs tronco`: piso ~**0,30 u**, pico **0,414 u** (`wake`/`wave`) → excedente ~**0,11 u**;
   - `antebraço vs cabeça`: piso ~**0,18 u**, pico **0,282 u** (`wake`) → excedente ~**0,10 u**;
   - `mão vs tronco`, `antebraço/mão vs portinha`: excedentes abaixo de ~0,10 u.

O detector, como calibrado hoje (`LIMIAR_PENETRACAO_U = 0,020 u`, sem desconto do piso por par), **não distingue** (1) de (2): ele entregaria à correção, em todas as poses, os ~0,45 u e os 0,195 u do piso estrutural. Ligar uma correção amortecida sobre esses números brutos empurraria os membros de forma **constante e visível por causa do piso**, não por causa de uma interpenetração real dirigida pela pose — justamente o tipo de movimento não solicitado e o "efeito duro" que o projeto acabou de combater. Mexer no que o usuário vê a partir de evidência que não isola o defeito real é uma decisão de produto que não cabe fechar aqui.

O excedente dirigido pela pose existe e é recorrente (sobretudo `interaction:wake`, `flourish:wave`, `idle:curious/stylish/fighter`, `dance`), mas é **pequeno** (0,10–0,25 u) e **só aparece depois de descontar o piso estrutural** — o que o detector ainda não faz. Portanto a pré-condição do FEAT-002 ("os números comprovarem interpenetração real e recorrente" de forma isolável) **não está satisfeita com a calibração atual**.

### O que foi entregue mesmo assim (caminho SEMPRE do FEAT-002)

`src/sejoga/colisao_membros.py` → `resolver_colisoes(pose, partes, parametros)`: função **pura e inerte** que, a partir das colisões detectadas, empurra o **alvo** do membro para fora da colisão ao longo da menor separação até `raio + FOLGA_U` (espelha `tentacle_constraints.ObstacleBox.project`) e **reorienta o membro o mínimo** para a ponta alcançar o alvo empurrado — move o alvo, nunca salta o ângulo; o deslocamento é proporcional à penetração, logo some a zero quando não há colisão. **Nada no projeto a chama por padrão.** O docstring descreve passo a passo como ligá-la ao fim de `AnimationController.update` com mola amortecida (`body_motion.Spring`/`joint_springs.SpringPose`) quando a evidência passar a justificar. Teste `tests/test_colisao_membros.py::test_resolver_colisoes_reduz_penetracao_capsula_caixa` prova que ela reduz a penetração de uma pose sintética sobreposta; outros dois provam que não altera poses sem colisão e que é pura.

### Pré-condição para reabrir a correção (recalibração recomendada)

Antes de ligar a correção, recalibrar o detector para que a profundidade medida seja **só o excedente dirigido pela pose**:

- descontar o **piso estrutural por par** (subtrair a profundidade medida no repouso de cada par), ou
- **encolher a cápsula do membro perto da raiz** / **afundar menos a origem na caixa** (ajustar `RAIOS_MEMBRO`, `MEIA_DIM_TRONCO`/`CABECA`, origem dos volumes), de modo que o piso caia para ~0 e só o excedente conte.

Com isso, `PARES_A_CHECAR` e `LIMIAR_PENETRACAO_U` passam a flagrar apenas a interpenetração real; aí o excedente de 0,10–0,25 u nos pares `braço dir. vs braço esq.`, `antebraço vs tronco` e `antebraço vs cabeça` (piores em `interaction:wake`) justifica ligar `resolver_colisoes` com mola, e o FEAT-002 deve então acrescentar o teste de ausência de tranco via `tools/analisar_anim.detectar_trancos` (`LIMIAR_JERK_TRANCO`).

## Validação visual pendente (GPU)

A "naturalidade" do movimento — se a pose corrigida *parece* natural — **só se valida na GPU** e não foi verificada aqui: esta máquina pode cair para `p3tinydisplay` (sem GPU real). Como a correção não foi ligada, não há mudança visual a validar neste passo; se a correção for reativada após a recalibração, abrir o executável e conferir render/captura é obrigatório antes de aceitar o resultado.

## Parâmetros calibráveis (todos em `src/sejoga/colisao_membros.py`, bloco PARÂMETROS)

Detecção:

- `RAIOS_MEMBRO`, `RAIO_MEMBRO_PADRAO` — raio da cápsula por membro.
- `MEIA_DIM_TRONCO`, `MEIA_DIM_CABECA`, `MEIA_DIM_PORTA` — meias-dimensões das caixas orientadas.
- `AMOSTRAS_CAPSULA_CAIXA` — densidade da amostragem cápsula-vs-caixa.
- `LIMIAR_PENETRACAO_U` — profundidade mínima para contar como colisão.
- `PARES_A_CHECAR` — pares plausíveis varridos.

Correção (usados só por `resolver_colisoes`, inerte):

- `FORCA_CORRECAO` — fração da penetração removida por aplicação (1.0 = até zerar + folga).
- `FOLGA_U` — folga extra deixada entre os volumes após corrigir.
- tensão da mola — ao ligar a correção, viria de `spring_tuning` (frequência/amortecimento por junta), guardada entre frames no controller.
