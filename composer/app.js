import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const params = new URLSearchParams(location.search);
const assetRoot = params.get("assets") || "../build/catalog-showroom/glb";
const $ = (id) => document.getElementById(id);
const state = { manifest: null, contract: null, components: new Map(), nodes: [], connections: [], selectedNode: null, selectedProvider: null, objects: new Map() };

const scene = new THREE.Scene(); scene.background = new THREE.Color(0x111923);
const camera = new THREE.PerspectiveCamera(48, 1, .01, 100); camera.position.set(.55, -.75, .55);
const renderer = new THREE.WebGLRenderer({ antialias:true }); renderer.setPixelRatio(devicePixelRatio); $("viewport").append(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement); controls.target.set(0,0,.04); controls.update();
scene.add(new THREE.HemisphereLight(0xd9efff, 0x293442, 2.3)); const light = new THREE.DirectionalLight(0xffffff, 2); light.position.set(2,-2,3); scene.add(light);
const grid = new THREE.GridHelper(1.2, 24, 0x36526a, 0x25394a); grid.rotation.x = Math.PI / 2; scene.add(grid);
const root = new THREE.Group(); scene.add(root); const loader = new GLTFLoader(); const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2();

function resize() { const box=$("viewport").getBoundingClientRect(); renderer.setSize(box.width,box.height); camera.aspect=box.width/box.height; camera.updateProjectionMatrix(); } addEventListener("resize",resize); resize();
function animate(){ requestAnimationFrame(animate); renderer.render(scene,camera); } animate();
function key(kind,id){ return `${kind}:${id}`; }
function component(kind,id){ return state.components.get(key(kind,id)); }
function rule(provider, consumer) { return state.contract.connection_rules.find((entry) => entry.provider_interface===provider.interface && entry.consumer_interface===consumer.interface && entry.status==="compatible"); }
function port(node, id, role) { return component(node.kind,node.product).assembly_ports.find((entry)=>entry.id===id && entry.role===role); }
function node(id){ return state.nodes.find((entry)=>entry.id===id); }
function used(nodeId, portId){ return state.connections.filter((entry)=>entry.provider.node===nodeId && entry.provider.port===portId).length; }
function poseMatrix(pose){ const [r,p,y]=pose.rpy_deg.map((v)=>THREE.MathUtils.degToRad(v)); return new THREE.Matrix4().compose(new THREE.Vector3(...pose.position_m),new THREE.Quaternion().setFromEuler(new THREE.Euler(r,p,y,"ZYX")),new THREE.Vector3(1,1,1)); }
function connectionFor(id){ return state.connections.find((entry)=>entry.consumer.node===id); }
function worldMatrix(id, seen=new Set()) { if(seen.has(id)) return new THREE.Matrix4(); seen.add(id); const n=node(id); const connection=connectionFor(id); if(!connection) return new THREE.Matrix4(); const providerNode=node(connection.provider.node); const provider=port(providerNode,connection.provider.port,"provider"); const consumer=port(n,connection.consumer.port,"consumer"); const adjustment={position_m:connection.adjustment.position_m,rpy_deg:connection.adjustment.rpy_deg}; return worldMatrix(providerNode.id,seen).multiply(poseMatrix(provider.pose)).multiply(poseMatrix(adjustment)).multiply(poseMatrix(consumer.pose).invert()); }
function compatibleTargets(part) { const consumerPorts=part.assembly_ports.filter((p)=>p.role==="consumer"); return state.nodes.flatMap((providerNode)=>component(providerNode.kind,providerNode.product).assembly_ports.filter((p)=>p.role==="provider" && used(providerNode.id,p.id)<p.capacity).flatMap((provider)=>consumerPorts.filter((consumer)=>rule(provider,consumer)).map((consumer)=>({providerNode,provider,consumer,rule:rule(provider,consumer)}))); }
function rotor(index){ return {index, name:`prop${index}`, rotation_direction:index%2? -1:1}; }
function removeNode(entry){ state.nodes=state.nodes.filter((n)=>n.id!==entry.id); state.connections=state.connections.filter((c)=>c.provider.node!==entry.id && c.consumer.node!==entry.id); }
function addPart(kind,id) {
  const part=component(kind,id);
  if(kind==="frame") {
    if(state.nodes.some((n)=>n.kind==="frame")) return setStatus("Frameは一機体につき一つです。");
    state.nodes.push({id:"frame",kind,product:id}); return redraw();
  }
  if(!state.nodes.some((n)=>n.kind==="frame")) return setStatus("先にFrameを置いてください。");
  if(["battery","camera","controller","landing_gear"].includes(kind)) {
    state.nodes.filter((n)=>n.kind===kind).forEach(removeNode);
  }
  const targets=compatibleTargets(part);
  const selected=state.selectedProvider && targets.find((target)=>target.providerNode.id===state.selectedProvider.node && target.provider.id===state.selectedProvider.port);
  const target=selected||targets[0];
  if(!target) return setStatus("接続可能な未使用portがありません。");
  const ordinal=state.nodes.filter((n)=>n.kind===kind).length+1;
  const entry={id:`${kind}_${ordinal}`,kind,product:id};
  if(kind==="motor") entry.rotor=rotor(state.nodes.filter((n)=>n.kind==="motor").length+1);
  state.nodes.push(entry);
  state.connections.push({provider:{node:target.providerNode.id,port:target.provider.id},consumer:{node:entry.id,port:target.consumer.id},adjustment:{position_m:[0,0,0],rpy_deg:[0,0,0]}});
  state.selectedNode=entry.id; state.selectedProvider=null; redraw();
}
function setStatus(message){ $("status").textContent=message; }
function cardList(){ const cards=$("cards"); cards.replaceChildren(); const template=$("card"); for(const item of state.manifest.items){ const card=template.content.firstElementChild.cloneNode(true); card.querySelector("strong").textContent=item.name; card.querySelector("small").textContent=item.kind; card.querySelector("p").textContent=Object.entries(item.specs).slice(0,2).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join("×"):v}`).join(" · "); card.addEventListener("dragstart",(event)=>event.dataTransfer.setData("text/plain",JSON.stringify({kind:item.kind,id:item.id}))); card.addEventListener("click",()=>addPart(item.kind,item.id)); cards.append(card); } }
async function objectFor(n){ const item=state.manifest.items.find((entry)=>entry.kind===n.kind&&entry.id===n.product); const group=new THREE.Group(); group.userData.nodeId=n.id; root.add(group); state.objects.set(n.id,group); try { const gltf=await loader.loadAsync(`${assetRoot}/${item.asset}`); group.add(gltf.scene); } catch(error) { const fallback=new THREE.Mesh(new THREE.BoxGeometry(.04,.04,.02),new THREE.MeshStandardMaterial({color:0x49a9d4})); group.add(fallback); console.warn(error); } }
function addPortMarkers(n, group){ const part=component(n.kind,n.product); for(const p of part.assembly_ports.filter((entry)=>entry.role==="provider")){ const marker=new THREE.Mesh(new THREE.SphereGeometry(.008,12,8),new THREE.MeshBasicMaterial({color:used(n.id,p.id)>=p.capacity?0x596673:0x53d8ff})); marker.position.fromArray(p.pose.position_m); marker.userData.provider={node:n.id,port:p.id}; group.add(marker); } }
async function redraw(){ root.clear(); state.objects.clear(); for(const n of state.nodes) await objectFor(n); for(const n of state.nodes){ const group=state.objects.get(n.id); group.matrixAutoUpdate=false; group.matrix.copy(worldMatrix(n.id)); group.matrix.decompose(group.position,group.quaternion,group.scale); group.matrixAutoUpdate=true; addPortMarkers(n,group); } inspector(); graph(); setStatus(`${state.nodes.length} parts · ${state.connections.length} connections`); }
function vectorFields(label, value, units, allowedAxes, limits, change){
  const wrapper=document.createElement("label");
  wrapper.className="field";
  wrapper.innerHTML=`<span>${label}</span><span class="triplet"></span>`;
  const names=units==="cm"?["x","y","z"]:["roll","pitch","yaw"];
  value.forEach((number,index)=>{
    const input=document.createElement("input");
    const scale=units==="cm"?100:1;
    const allowed=allowedAxes.includes(names[index]);
    const limit=limits?.[index];
    input.type="number";
    input.step=units==="cm"?"0.1":"1";
    input.value=(number*scale).toFixed(units==="cm"?2:1);
    input.title=names[index];
    input.disabled=!allowed;
    if(Number.isFinite(limit)) {
      input.min=String(-limit*scale);
      input.max=String(limit*scale);
    }
    input.onchange=()=>{
      const raw=Number(input.value)/scale;
      const constrained=Number.isFinite(limit) ? Math.max(-limit,Math.min(limit,raw)) : raw;
      input.value=(constrained*scale).toFixed(units==="cm"?2:1);
      change(index,constrained);
    };
    wrapper.querySelector(".triplet").append(input);
  });
  return wrapper;
}
function inspector(){
  const panel=$("selection");
  panel.replaceChildren();
  const selected=node(state.selectedNode);
  if(!selected) {
    panel.className="empty";
    panel.textContent="部品またはportを選択してください。";
    return;
  }
  panel.className="";
  const part=component(selected.kind,selected.product);
  panel.innerHTML=`<strong>${part.name || selected.product}</strong><p class="port">${selected.kind} / ${selected.id}</p>`;
  const connection=connectionFor(selected.id);
  if(connection){
    const provider=port(node(connection.provider.node),connection.provider.port,"provider");
    const consumer=port(selected,connection.consumer.port,"consumer");
    const rule=state.contract.connection_rules.find((entry)=>
      entry.provider_interface===provider.interface && entry.consumer_interface===consumer.interface
    );
    const adjustment=rule?.adjustment || {translation_axes:[],rotation_axes:[]};
    panel.append(vectorFields("位置 cm",connection.adjustment.position_m,"cm",adjustment.translation_axes,adjustment.translation_limits_m,(i,v)=>{ connection.adjustment.position_m[i]=v; redraw(); }));
    panel.append(vectorFields("RPY deg",connection.adjustment.rpy_deg,"deg",adjustment.rotation_axes,adjustment.rotation_limits_deg,(i,v)=>{ connection.adjustment.rpy_deg[i]=v; redraw(); }));
    const translation=rule?.adjustment.translation_axes.join(",") || "固定";
    const rotation=rule?.adjustment.rotation_axes.join(",") || "固定";
    panel.insertAdjacentHTML("beforeend",`<p class="hint">接続: ${connection.provider.node}.${connection.provider.port}<br>許可: ${translation} / ${rotation}</p>`);
  }
  if(selected.kind==="motor") panel.insertAdjacentHTML("beforeend",`<p class="hint">Rotor: ${selected.rotor.name} / ${selected.rotor.rotation_direction>0?"CCW":"CW"}</p>`);
}
function graph(){ $("graph").textContent=JSON.stringify({schema_version:1,kind:"fpv-assembly",name:"composer-draft",type:"quad_x",controller_mode:"angle",nodes:state.nodes,connections:state.connections},null,2); }
function exportGraph(){ const blob=new Blob([$("graph").textContent],{type:"application/json"}); const link=Object.assign(document.createElement("a"),{href:URL.createObjectURL(blob),download:"fpv-assembly.json"}); link.click(); URL.revokeObjectURL(link.href); }
$("viewport").addEventListener("dragover",(event)=>event.preventDefault()); $("viewport").addEventListener("drop",(event)=>{ event.preventDefault(); try{const {kind,id}=JSON.parse(event.dataTransfer.getData("text/plain")); addPart(kind,id);}catch{setStatus("Drop dataが不正です。");} });
renderer.domElement.addEventListener("pointerdown",(event)=>{ const rect=renderer.domElement.getBoundingClientRect(); pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1); raycaster.setFromCamera(pointer,camera); const hit=raycaster.intersectObjects(root.children,true)[0]; if(!hit) return; let current=hit.object; while(current && !current.userData.nodeId && !current.userData.provider) current=current.parent; if(current?.userData.provider){state.selectedProvider=current.userData.provider; setStatus(`接続先: ${state.selectedProvider.node}.${state.selectedProvider.port}`);} else if(current?.userData.nodeId){state.selectedNode=current.userData.nodeId; inspector();} });
$("save").onclick=()=>localStorage.setItem("hakoniwa-fpv-composer",$("graph").textContent); $("export").onclick=exportGraph; $("import").onchange=(event)=>{ const file=event.target.files[0]; if(!file)return; const reader=new FileReader(); reader.onload=()=>{ try { const data=JSON.parse(reader.result); state.nodes=data.nodes||[]; state.connections=data.connections||[]; redraw(); } catch {setStatus("Assembly Graph JSONを読み込めませんでした。");} }; reader.readAsText(file); };
async function boot(){ try { const [manifest,contract]=await Promise.all([fetch(`${assetRoot}/manifest.json`).then(r=>r.json()),fetch(`${assetRoot}/assembly-contract.json`).then(r=>r.json())]); state.manifest=manifest; state.contract=contract; for(const entry of contract.components) state.components.set(key(entry.kind,entry.id),entry); for(const entry of manifest.items){ const target=component(entry.kind,entry.id); if(target) Object.assign(target,{name:entry.name,description:entry.description,specs:entry.specs}); } cardList(); const saved=localStorage.getItem("hakoniwa-fpv-composer"); if(saved){const draft=JSON.parse(saved);state.nodes=draft.nodes||[];state.connections=draft.connections||[];await redraw();} else setStatus("Frameを選んでComposerを始めてください。"); } catch(error) { console.error(error); setStatus(`Catalogを読めません: ${error.message}`); } }
boot();
