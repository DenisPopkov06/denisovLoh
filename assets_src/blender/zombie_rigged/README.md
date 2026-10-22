# zombie_walker_rigged

Source of `public/models/characters/zombie_walker_rigged.glb` (rigged zombie with
`walk` / `attack` / `death` clips). The scene is `../zombie_rigged.blend`.

Scripts run inside Blender (e.g. sent through the MCP add-on socket with
`blender_rpc.py`, code on stdin), in this order:

1. `slim_body.py` — thins the body toward the bone axes (original mesh kept as `mesh_zombie1_0_orig`).
2. `build_clothes.py` — shirt, shorts and belt grown from the body mesh by bone weights.
3. `face_skin.py` — bone-tan skin, dark eye sockets, glowing eyes, open jaw in the walk.
4. `zombie_walk.py`, `make_actions.py`, `walk_game.py` — stagger walk, attack, death and the in-place game walk.
5. `bake_export.py` — bakes the node materials to textures, scales to 1.8 m and exports the GLB
   (one NLA track per clip). Run it on a copy of the scene: it replaces the materials with baked ones.
