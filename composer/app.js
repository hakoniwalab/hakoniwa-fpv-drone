import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const params = new URLSearchParams(location.search);
const assetRoot = params.get("assets") || "../build/catalog-showroom/glb";
const $ = (id) => document.getElementById(id);
const state = { manifest: null, contract: null, components: new Map(), nodes: [], connections: [], selectedNode: null, selectedProvider: null, objects: new Map(), previews: [] };

const scene = new THREE.Scene(); scene.background = new THREE.Color(0x526d82);
const camera = new THREE.PerspectiveCamera(48, 1, .01, 100); camera.position.set(.55, -.75, .55);
const renderer = new THREE.WebGLRenderer({ antialias:true }); renderer.setPixelRatio(devicePixelRatio); renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.3; $("viewport").append(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement); controls.target.set(0,0,.04); controls.update();
scene.add(new THREE.HemisphereLight(0xf1f8ff, 0x5b7180, 3.2)); const light = new THREE.DirectionalLight(0xffffff, 3.5); light.position.set(2,-2,3); scene.add(light); const fillLight=new THREE.DirectionalLight(0xb9ddff,2); fillLight.position.set(-2,1,1); scene.add(fillLight);
const grid = new THREE.GridHelper(1.2, 24, 0x79a8c5, 0x42667d); grid.rotation.x = Math.PI / 2; scene.add(grid);
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
function compatibleTargets(part, includeOccupied=false) {
  const consumerPorts=part.assembly_ports.filter((entry)=>entry.role==="consumer");
  return state.nodes.flatMap((providerNode)=>{
    const providerPorts=component(providerNode.kind,providerNode.product).assembly_ports.filter((entry)=>
      entry.role==="provider" && (includeOccupied || used(providerNode.id,entry.id)<entry.capacity)
    );
    return providerPorts.flatMap((provider)=>consumerPorts
      .filter((consumer)=>rule(provider,consumer))
      .map((consumer)=>({providerNode,provider,consumer,rule:rule(provider,consumer)}))
    );
  });
}
function rotor(index){ return {index, name:`prop${index}`, rotation_direction:index%2? -1:1}; }
function removeNode(entry){ state.nodes=state.nodes.filter((n)=>n.id!==entry.id); state.connections=state.connections.filter((c)=>c.provider.node!==entry.id && c.consumer.node!==entry.id); }
function deleteNodeWithoutConfirmation(id) {
  const removed=new Set([id]);
  for(let changed=true; changed;) {
    changed=false;
    for(const connection of state.connections) {
      if(removed.has(connection.provider.node) && !removed.has(connection.consumer.node)) {
        removed.add(connection.consumer.node);
        changed=true;
      }
    }
  }
  state.nodes=state.nodes.filter((entry)=>!removed.has(entry.id));
  state.connections=state.connections.filter((connection)=>!removed.has(connection.provider.node) && !removed.has(connection.consumer.node));
  if(removed.has(state.selectedNode)) state.selectedNode=null;
  if(state.selectedProvider && removed.has(state.selectedProvider.node)) state.selectedProvider=null;
  return removed;
}
function deleteNode(id) {
  const target=node(id);
  if(!target) return;
  const label=component(target.kind,target.product).name || target.product;
  const message=target.kind==="frame" ? "Frameを削除すると、すべての部品を取り外します。" : `${label}を削除しますか？ 接続先の部品も取り外される場合があります。`;
  if(!confirm(message)) return;
  deleteNodeWithoutConfirmation(id);
  redraw();
  cardList();
}
function isMotorMount(provider) { return provider.interface.endsWith(".motor-mount"); }
function isPropellerShaft(provider) { return provider.interface.endsWith(".propeller-shaft"); }
function nextRotorIndex() { return Math.max(0,...state.nodes.filter((entry)=>entry.kind==="motor").map((entry)=>entry.rotor?.index || 0))+1; }
function addMotorSet(part, id) {
  const selected=selectedProviderPort();
  if(!selected) return;
  const mounts=component(selected.node.kind,selected.node.product).assembly_ports.filter((provider)=>
    provider.role==="provider" && provider.interface===selected.port.interface && isMotorMount(provider)
  );
  const consumer=part.assembly_ports.find((entry)=>entry.role==="consumer" && rule(selected.port,entry));
  if(!consumer || !mounts.length) return setStatus("Motor mount の接続定義を解決できません。");
  const occupied=mounts.flatMap((provider)=>state.connections.filter((connection)=>
    connection.provider.node===selected.node.id && connection.provider.port===provider.id
  ));
  if(occupied.length && !confirm(`既存の ${occupied.length} 個の Motor を、${part.name} に置き換えますか？`)) return;
  for(const connection of occupied) deleteNodeWithoutConfirmation(connection.consumer.node);
  let rotorIndex=nextRotorIndex();
  for(const provider of mounts) {
    if(used(selected.node.id,provider.id)>=provider.capacity) continue;
    const ordinal=state.nodes.filter((entry)=>entry.kind==="motor").length+1;
    const entry={id:`motor_${ordinal}`,kind:"motor",product:id,rotor:rotor(rotorIndex++)};
    state.nodes.push(entry);
    state.connections.push({provider:{node:selected.node.id,port:provider.id},consumer:{node:entry.id,port:consumer.id},adjustment:{position_m:[0,0,0],rpy_deg:[0,0,0]}});
  }
  state.selectedNode=selected.node.id;
  state.selectedProvider=null;
  cardList();
  redraw();
}
function addPropellerSet(part, id) {
  const selected=selectedProviderPort();
  if(!selected) return;
  const shafts=state.nodes.filter((entry)=>entry.kind==="motor").flatMap((motor)=>
    component(motor.kind,motor.product).assembly_ports.filter((provider)=>
      provider.role==="provider" && provider.interface===selected.port.interface && isPropellerShaft(provider)
    ).map((provider)=>({motor,provider}))
  );
  const consumer=part.assembly_ports.find((entry)=>entry.role==="consumer" && rule(selected.port,entry));
  if(!consumer || !shafts.length) return setStatus("Propeller shaft の接続定義を解決できません。");
  const occupied=shafts.flatMap(({motor,provider})=>state.connections.filter((connection)=>
    connection.provider.node===motor.id && connection.provider.port===provider.id
  ));
  if(occupied.length && !confirm(`既存の ${occupied.length} 枚の Propeller を、${part.name} に置き換えますか？`)) return;
  for(const connection of occupied) deleteNodeWithoutConfirmation(connection.consumer.node);
  for(const {motor,provider} of shafts) {
    if(used(motor.id,provider.id)>=provider.capacity) continue;
    const ordinal=state.nodes.filter((entry)=>entry.kind==="propeller").length+1;
    const entry={id:`propeller_${ordinal}`,kind:"propeller",product:id};
    state.nodes.push(entry);
    state.connections.push({provider:{node:motor.id,port:provider.id},consumer:{node:entry.id,port:consumer.id},adjustment:{position_m:[0,0,0],rpy_deg:[0,0,0]}});
  }
  state.selectedNode=state.nodes.find((entry)=>entry.kind==="frame")?.id || null;
  state.selectedProvider=null;
  cardList();
  redraw();
}
function addPart(kind,id) {
  const part=component(kind,id);
  if(kind==="frame") {
    if(state.nodes.some((n)=>n.kind==="frame")) return setStatus("Frameは一機体につき一つです。");
    state.nodes.push({id:"frame",kind,product:id});
    state.selectedNode="frame";
    state.selectedProvider=null;
    cardList();
    return redraw();
  }
  if(!state.nodes.some((n)=>n.kind==="frame")) return setStatus("先にFrameを置いてください。");
  if(kind==="motor" && state.selectedProvider?.motorBatch) return addMotorSet(part,id);
  if(kind==="propeller" && state.selectedProvider?.propellerBatch) return addPropellerSet(part,id);
  if(["battery","camera","controller","landing_gear"].includes(kind)) {
    state.nodes.filter((n)=>n.kind===kind).forEach(removeNode);
  }
  const targets=compatibleTargets(part,Boolean(state.selectedProvider));
  const selected=state.selectedProvider && targets.find((target)=>target.providerNode.id===state.selectedProvider.node && target.provider.id===state.selectedProvider.port);
  const target=selected||targets[0];
  if(!target) return setStatus("接続可能な未使用portがありません。");
  if(used(target.providerNode.id,target.provider.id)>=target.provider.capacity) {
    const attached=state.connections.filter((connection)=>connection.provider.node===target.providerNode.id && connection.provider.port===target.provider.id);
    const attachedNames=attached.map((connection)=>component(node(connection.consumer.node).kind,node(connection.consumer.node).product).name).join("、");
    if(!confirm(`${target.provider.id} は ${attachedNames} に使用されています。置き換えますか？`)) return;
    for(const connection of attached) deleteNodeWithoutConfirmation(connection.consumer.node);
  }
  const ordinal=state.nodes.filter((n)=>n.kind===kind).length+1;
  const entry={id:`${kind}_${ordinal}`,kind,product:id};
  if(kind==="motor") entry.rotor=rotor(state.nodes.filter((n)=>n.kind==="motor").length+1);
  state.nodes.push(entry);
  state.connections.push({provider:{node:target.providerNode.id,port:target.provider.id},consumer:{node:entry.id,port:target.consumer.id},adjustment:{position_m:[0,0,0],rpy_deg:[0,0,0]}});
  state.selectedNode=target.providerNode.id; state.selectedProvider=null; cardList(); redraw();
}
function setStatus(message){ $("status").textContent=message; }
function clearPreviews() { for(const renderer of state.previews) renderer.dispose(); state.previews=[]; }
async function cardPreview(item, host) {
  const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true});
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  renderer.setSize(74,58,false);
  host.append(renderer.domElement);
  state.previews.push(renderer);
  const previewScene=new THREE.Scene();
  const previewCamera=new THREE.PerspectiveCamera(35,74/58,.001,10);
  previewScene.add(new THREE.HemisphereLight(0xe8f7ff,0x23313e,2.5));
  const light=new THREE.DirectionalLight(0xffffff,2); light.position.set(1,1,2); previewScene.add(light);
  try {
    const gltf=await loader.loadAsync(`${assetRoot}/${item.asset}`);
    const model=gltf.scene;
    const bounds=new THREE.Box3().setFromObject(model);
    const center=bounds.getCenter(new THREE.Vector3());
    const size=bounds.getSize(new THREE.Vector3());
    const extent=Math.max(size.x,size.y,size.z,.02);
    model.position.sub(center);
    previewScene.add(model);
    previewCamera.position.set(extent*1.5,-extent*1.5,extent*1.1);
    previewCamera.lookAt(0,0,0);
    renderer.render(previewScene,previewCamera);
  } catch(error) { console.warn(`Preview unavailable: ${item.id}`,error); }
}
function selectedProviderPort() {
  if(!state.selectedProvider) return null;
  const providerNode=node(state.selectedProvider.node);
  return providerNode ? {node:providerNode,port:port(providerNode,state.selectedProvider.port,"provider")} : null;
}
function candidateItems() {
  if(!state.nodes.some((entry)=>entry.kind==="frame")) return state.manifest.items.filter((item)=>item.kind==="frame");
  const selected=selectedProviderPort();
  if(!selected) return [];
  return state.manifest.items.filter((item)=>{
    const part=component(item.kind,item.id);
    return part.assembly_ports.some((consumer)=>consumer.role==="consumer" && rule(selected.port,consumer));
  });
}
function cardList(){
  clearPreviews();
  const cards=$("cards");
  cards.replaceChildren();
  const hint=$("catalog-hint");
  const items=candidateItems();
  if(!items.length) {
    hint.textContent=state.nodes.some((entry)=>entry.kind==="frame") ? "右の Connectable Ports から、接続先を選択してください。" : "最初に Frame を選択してください。";
    return;
  }
  const selected=selectedProviderPort();
  hint.textContent=selected ? `${selected.node.id}.${selected.port.id} に接続できる部品` : "Frame を選択してください。";
  const template=$("card");
  for(const item of items){
    const card=template.content.firstElementChild.cloneNode(true);
    card.querySelector("strong").textContent=item.name;
    card.querySelector("small").textContent=item.kind;
    card.querySelector("p").textContent=Object.entries(item.specs).slice(0,2).map(([k,v])=>`${k}: ${Array.isArray(v)?v.join("×"):v}`).join(" · ");
    card.addEventListener("click",()=>addPart(item.kind,item.id));
    cards.append(card);
    cardPreview(item,card.querySelector(".preview"));
  }
}
function visualDockingOffset(n, item) {
  const connection=connectionFor(n.id);
  if(n.kind!=="propeller" || !connection) return 0;
  const providerNode=node(connection.provider.node);
  if(providerNode?.kind!=="motor") return 0;
  const providerItem=state.manifest.items.find((entry)=>entry.kind===providerNode.kind && entry.id===providerNode.product);
  const motorTop=providerItem?.bounds_m?.[1]?.[2];
  const propellerBottom=item.bounds_m?.[0]?.[2];
  if(!Number.isFinite(motorTop) || !Number.isFinite(propellerBottom)) return 0;
  return Math.max(0,motorTop-propellerBottom);
}
async function objectFor(n){ const item=state.manifest.items.find((entry)=>entry.kind===n.kind&&entry.id===n.product); const group=new THREE.Group(); group.userData.nodeId=n.id; root.add(group); state.objects.set(n.id,group); try { const gltf=await loader.loadAsync(`${assetRoot}/${item.asset}`); gltf.scene.position.z=visualDockingOffset(n,item); group.add(gltf.scene); } catch(error) { const fallback=new THREE.Mesh(new THREE.BoxGeometry(.04,.04,.02),new THREE.MeshStandardMaterial({color:0x49a9d4})); group.add(fallback); console.warn(error); } return group; }
async function redraw(){ root.clear(); state.objects.clear(); for(const n of state.nodes){ const group=await objectFor(n); group.matrixAutoUpdate=false; group.matrix.copy(worldMatrix(n.id)); group.matrix.decompose(group.position,group.quaternion,group.scale); group.matrixAutoUpdate=true; } inspector(); portList(); assemblyList(); graph(); setStatus(`${state.nodes.length} parts · ${state.connections.length} connections`); }
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
function portList() {
  const container=$("ports");
  const clear=$("clear-port");
  container.replaceChildren();
  const selected=node(state.selectedNode);
  if(!selected) {
    container.className="empty";
    container.textContent="部品を選択すると接続先portを表示します。";
    clear.hidden=true;
    return;
  }
  const providerPorts=component(selected.kind,selected.product).assembly_ports.filter((entry)=>entry.role==="provider");
  if(!providerPorts.length) {
    container.className="empty";
    container.textContent="この部品には接続先となる provider port がありません。";
    clear.hidden=true;
    return;
  }
  container.className="";
  clear.hidden=!state.selectedProvider;
  const motorMounts=providerPorts.filter(isMotorMount);
  const appendPort=(provider, titleText, providers=[provider], motorBatch=false)=>{
    const button=document.createElement("button");
    const isSelected=state.selectedProvider?.node===selected.id && state.selectedProvider.port===provider.id && Boolean(state.selectedProvider.motorBatch)===motorBatch;
    button.className=`port-row${isSelected ? " selected" : ""}`;
    const title=document.createElement("strong"); title.textContent=titleText;
    const detail=document.createElement("small");
    const attached=state.connections.filter((connection)=>connection.provider.node===selected.id && providers.some((entry)=>entry.id===connection.provider.port))
      .map((connection)=>component(node(connection.consumer.node).kind,node(connection.consumer.node).product).name);
    const capacity=providers.reduce((sum,entry)=>sum+entry.capacity,0);
    const usedCount=providers.reduce((sum,entry)=>sum+used(selected.id,entry.id),0);
    detail.textContent=`${provider.interface} · ${usedCount}/${capacity}${attached.length ? ` · ${attached.join("、")}` : ""}`;
    button.append(title,detail);
    button.onclick=()=>{
      state.selectedProvider=isSelected ? null : {node:selected.id,port:provider.id,motorBatch};
      portList();
      cardList();
      setStatus(state.selectedProvider ? `接続先: ${motorBatch ? "Motors" : `${selected.id}.${provider.id}`}` : "接続先を選択解除しました。");
    };
    container.append(button);
  };
  if(motorMounts.length) appendPort(motorMounts[0],`Motors (${motorMounts.length} mount ports)`,motorMounts,true);
  for(const provider of providerPorts.filter((entry)=>!isMotorMount(entry))) {
    appendPort(provider,provider.id);
  }
  if(selected.kind==="frame") {
    const shafts=state.nodes.filter((entry)=>entry.kind==="motor").flatMap((motor)=>
      component(motor.kind,motor.product).assembly_ports.filter((provider)=>provider.role==="provider" && isPropellerShaft(provider))
        .map((provider)=>({motor,provider}))
    );
    if(shafts.length) {
      const first=shafts[0];
      const button=document.createElement("button");
      const isSelected=state.selectedProvider?.node===first.motor.id && state.selectedProvider.port===first.provider.id && state.selectedProvider.propellerBatch;
      button.className=`port-row${isSelected ? " selected" : ""}`;
      const title=document.createElement("strong"); title.textContent=`Propellers (${shafts.length} shafts)`;
      const detail=document.createElement("small");
      const usedCount=shafts.reduce((sum,{motor,provider})=>sum+used(motor.id,provider.id),0);
      const attached=shafts.flatMap(({motor,provider})=>state.connections.filter((connection)=>connection.provider.node===motor.id && connection.provider.port===provider.id))
        .map((connection)=>component(node(connection.consumer.node).kind,node(connection.consumer.node).product).name);
      detail.textContent=`${first.provider.interface} · ${usedCount}/${shafts.length}${attached.length ? ` · ${attached.join("、")}` : ""}`;
      button.append(title,detail);
      button.onclick=()=>{
        state.selectedProvider=isSelected ? null : {node:first.motor.id,port:first.provider.id,propellerBatch:true};
        portList();
        cardList();
        setStatus(state.selectedProvider ? "接続先: Propellers" : "接続先を選択解除しました。");
      };
      container.append(button);
    }
  }
}
function assemblyList() {
  const container=$("assembly-list");
  const count=$("assembly-count");
  count.textContent=`${state.nodes.length} parts`;
  container.replaceChildren();
  if(!state.nodes.length) {
    container.className="empty";
    container.textContent="まだ部品はありません。";
    return;
  }
  container.className="";
  for(const entry of state.nodes) {
    const part=component(entry.kind,entry.product);
    const row=document.createElement("div");
    row.className=`assembly-row${entry.id===state.selectedNode ? " selected" : ""}`;
    const select=document.createElement("button");
    select.className="assembly-select";
    const name=document.createElement("strong");
    name.textContent=part.name || entry.product;
    const detail=document.createElement("small");
    detail.textContent=`${entry.kind} · ${entry.id}`;
    select.append(name,detail);
    select.onclick=()=>{ state.selectedNode=entry.id; state.selectedProvider=null; inspector(); portList(); assemblyList(); cardList(); };
    const remove=document.createElement("button");
    remove.className="delete-part";
    remove.textContent="削除";
    remove.title=`${part.name || entry.product}を削除`;
    remove.onclick=()=>deleteNode(entry.id);
    row.append(select,remove);
    container.append(row);
  }
}
function graph(){ $("graph").textContent=JSON.stringify({schema_version:1,kind:"fpv-assembly",name:"composer-draft",type:"quad_x",controller_mode:"angle",nodes:state.nodes,connections:state.connections},null,2); }
function exportGraph(){ const blob=new Blob([$("graph").textContent],{type:"application/json"}); const link=Object.assign(document.createElement("a"),{href:URL.createObjectURL(blob),download:"fpv-assembly.json"}); link.click(); URL.revokeObjectURL(link.href); }
renderer.domElement.addEventListener("pointerdown",(event)=>{ const rect=renderer.domElement.getBoundingClientRect(); pointer.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1); raycaster.setFromCamera(pointer,camera); const hit=raycaster.intersectObjects(root.children,true)[0]; if(!hit) return; let current=hit.object; while(current && !current.userData.nodeId && !current.userData.provider) current=current.parent; if(current?.userData.provider){state.selectedNode=current.userData.provider.node; state.selectedProvider=current.userData.provider; portList(); cardList(); setStatus(`接続先: ${state.selectedProvider.node}.${state.selectedProvider.port}`);} else if(current?.userData.nodeId){state.selectedNode=current.userData.nodeId; state.selectedProvider=null; inspector(); portList(); assemblyList(); cardList();} });
$("clear-port").onclick=()=>{ state.selectedProvider=null; portList(); cardList(); setStatus("接続先を選択解除しました。"); };
$("save").onclick=()=>localStorage.setItem("hakoniwa-fpv-composer",$("graph").textContent); $("export").onclick=exportGraph; $("import").onchange=(event)=>{ const file=event.target.files[0]; if(!file)return; const reader=new FileReader(); reader.onload=()=>{ try { const data=JSON.parse(reader.result); state.nodes=data.nodes||[]; state.connections=data.connections||[]; redraw(); } catch {setStatus("Assembly Graph JSONを読み込めませんでした。");} }; reader.readAsText(file); };
async function boot(){ try { const [manifest,contract]=await Promise.all([fetch(`${assetRoot}/manifest.json`).then(r=>r.json()),fetch(`${assetRoot}/assembly-contract.json`).then(r=>r.json())]); state.manifest=manifest; state.contract=contract; for(const entry of contract.components) state.components.set(key(entry.kind,entry.id),entry); for(const entry of manifest.items){ const target=component(entry.kind,entry.id); if(target) Object.assign(target,{name:entry.name,description:entry.description,specs:entry.specs}); } const saved=localStorage.getItem("hakoniwa-fpv-composer"); if(saved){const draft=JSON.parse(saved);state.nodes=draft.nodes||[];state.connections=draft.connections||[];state.selectedNode=state.nodes[0]?.id || null;await redraw();} else { assemblyList(); setStatus("Frameを選んでComposerを始めてください。"); } portList(); cardList(); } catch(error) { console.error(error); setStatus(`Catalogを読めません: ${error.message}`); } }
boot();
