/* Versioned visual recipes + local IndexedDB cards. No image uploads or backend. */
window.ObserverTemplates = (() => {
  'use strict';
  const FORMAT='image-observer-template', VERSION=1;
  const plain=value=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype;
  const uint=value=>Number.isInteger(value)&&value>=0&&value<=4294967295;
  const nameOf=value=>{
    if(typeof value!=='string'||!value.trim()||Array.from(value.trim()).length>40||/[\u0000-\u001f]/.test(value))throw new Error('模板名称需为1–40个字符。');
    return value.trim();
  };
  function init(api) {
    const status=document.getElementById('templateStatus'),personal=document.getElementById('personalCards'),official=document.getElementById('officialCards');
    const save=document.getElementById('saveTemplate'),file=document.getElementById('templateFile'),importButton=document.getElementById('importTemplate');
    const say=(text,error=false)=>{status.textContent=text;status.style.color=error?'#b42c34':'';};
    const schema=api.controls.map(el=>({id:el.id,type:el.type,options:el.tagName==='SELECT'?Array.from(el.options,o=>o.value):null,min:Number(el.min),max:Number(el.max),maxChars:el.id==='customText'?32:el.maxLength>0?el.maxLength:2048}));
    function validateRecipe(input) {
      if(!plain(input)||input.version!==VERSION||!plain(input.controls)||!plain(input.state))throw new Error('模板配方版本或结构不正确。');
      // Version 1 recipes predating group size retain their original 100% baseline.
      const sourceControls={...input.controls};
      if(!Object.hasOwn(sourceControls,'fragmentSize'))sourceControls.fragmentSize=100;
      if(Object.keys(sourceControls).length!==schema.length)throw new Error('模板参数缺失或不兼容。');
      const controls={};
      for(const item of schema) {
        if(!Object.hasOwn(sourceControls,item.id))throw new Error('模板参数缺失。');
        const value=sourceControls[item.id];
        if(item.options) {if(typeof value!=='string'||!item.options.includes(value))throw new Error('模板包含无效选项。');}
        else if(item.type==='range') {if(typeof value!=='number'||!Number.isInteger(value)||value<item.min||value>item.max)throw new Error('模板参数超出允许范围。');}
        else if(item.type==='checkbox') {if(typeof value!=='boolean')throw new Error('模板开关格式不正确。');}
        else if(typeof value!=='string'||Array.from(value).length>item.maxChars)throw new Error('模板文字过长或格式不正确。');
        controls[item.id]=value;
      }
      const s=input.state;
      if(!uint(s.visualRandomState)||!uint(s.textLayoutRevision)||!plain(s.wordState)||!api.words.includes(s.wordState.word)||!uint(s.wordState.rngState))throw new Error('模板随机状态不正确。');
      let policy=null;
      if(s.fragmentPolicy!==null) {
        if(!plain(s.fragmentPolicy))throw new Error('模板碎片状态不正确。');
        policy={};for(const key of ['cx','cy','rx','ry']) {const n=s.fragmentPolicy[key];if(!Number.isFinite(n)||n<0||n>1||((key==='rx'||key==='ry')&&n===0))throw new Error('模板碎片范围不正确。');policy[key]=n;}
      }
      return {version:VERSION,controls,state:{visualRandomState:s.visualRandomState,textLayoutRevision:s.textLayoutRevision,wordState:{word:s.wordState.word,rngState:s.wordState.rngState},fragmentPolicy:policy}};
    }
    let dbPromise;
    function database() {
      if(!dbPromise)dbPromise=new Promise((resolve,reject)=>{
        if(!window.indexedDB){reject(new Error('浏览器不支持本地模板存储。'));return;}
        let request;try{request=indexedDB.open('image-observer-templates',1);}catch(error){reject(error);return;}
        request.onupgradeneeded=()=>request.result.createObjectStore('templates',{keyPath:'id'});
        request.onerror=()=>reject(request.error||new Error('无法打开本地存储。'));
        request.onblocked=()=>reject(new Error('本地存储被其他页面占用，请关闭其他工具页面后重试。'));
        request.onsuccess=()=>{request.result.onversionchange=()=>request.result.close();resolve(request.result);};
      });
      return dbPromise;
    }
    async function transaction(mode,operation) {
      const db=await database();
      return new Promise((resolve,reject)=>{
        let tx,request;try{tx=db.transaction('templates',mode);request=operation(tx.objectStore('templates'));}catch(error){reject(error);return;}
        tx.oncomplete=()=>resolve(request.result);
        tx.onerror=tx.onabort=()=>reject(tx.error||request.error||new Error('本地存储操作失败。'));
      });
    }
    const blobURL=blob=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error('无法读取缩略图。'));reader.readAsDataURL(blob);});
    async function thumbnail(canvas) {
      const c=document.createElement('canvas'),scale=Math.min(1,320/Math.max(canvas.width,canvas.height));
      c.width=Math.max(1,Math.round(canvas.width*scale));c.height=Math.max(1,Math.round(canvas.height*scale));
      const ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(canvas,0,0,c.width,c.height);
      const blob=await new Promise(resolve=>c.toBlob(resolve,'image/jpeg',.72));c.width=c.height=1;
      if(!blob||blob.size>120000)throw new Error('无法生成轻量缩略图，请重试。');return blob;
    }
    // Read JPEG dimensions before decode, preventing giant or invalid imported images.
    async function validateThumbnail(value) {
      if(typeof value!=='string'||value.length>170000||!/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(value))throw new Error('缩略图格式或大小不正确。');
      let bytes;try{bytes=Uint8Array.from(atob(value.split(',')[1]),c=>c.charCodeAt(0));}catch(_){throw new Error('缩略图编码损坏。');}
      if(bytes.length>120000||bytes[0]!==255||bytes[1]!==216)throw new Error('缩略图不是有效 JPEG。');
      let dimensions=null;
      for(let i=2;i+8<bytes.length;) {
        if(bytes[i++]!==255)break;while(bytes[i]===255)i++;
        const marker=bytes[i++];if(marker===0xda||marker===0xd9)break;
        if(marker===0x01||(marker>=0xd0&&marker<=0xd7))continue;
        const length=(bytes[i]<<8)|bytes[i+1];if(length<2||i+length>bytes.length)break;
        if([0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf].includes(marker)){dimensions=[(bytes[i+5]<<8)|bytes[i+6],(bytes[i+3]<<8)|bytes[i+4]];break;}
        i+=length;
      }
      if(!dimensions||dimensions.some(n=>n<1||n>320))throw new Error('缩略图尺寸须在320px以内。');
      const image=new Image();image.src=value;try{await image.decode();}catch(_){throw new Error('缩略图无法解码。');}
      if(image.naturalWidth!==dimensions[0]||image.naturalHeight!==dimensions[1])throw new Error('缩略图尺寸无效。');
      return new Blob([bytes],{type:'image/jpeg'});
    }
    function button(text,action,className) {const b=document.createElement('button');b.type='button';b.textContent=text;if(className)b.className=className;b.onclick=action;return b;}
    const act=fn=>async()=>{try{await fn();}catch(error){say(`操作失败：${error.message||'请重试。'}`,true);}};
    function download(data,name) {
      const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    async function card(record,officialRecord=false) {
      const c=document.createElement('article');c.className='template-card';
      const apply=button(record.name,act(async()=>say(api.apply(validateRecipe(record.recipe)))),'apply-template');
      const img=document.createElement('img');img.alt=record.name;img.loading='lazy';
      img.src=officialRecord?record.thumbnail:await blobURL(record.thumbnail);apply.prepend(img,document.createElement('br'));c.append(apply);
      if(!officialRecord) {
        const actions=document.createElement('div');actions.className='actions';
        actions.append(button('重命名',act(async()=>{
          const name=prompt('模板名称（最多40个字符）',record.name);if(name===null)return;
          await transaction('readwrite',store=>store.put({...record,name:nameOf(name)}));await refresh();say('已重命名。');
        })),button('删除',act(async()=>{
          if(!confirm(`删除模板“${record.name}”？`))return;
          await transaction('readwrite',store=>store.delete(record.id));await refresh();say('已删除模板。');
        })),button('导出 JSON',act(async()=>{
          download({format:FORMAT,version:VERSION,name:record.name,recipe:validateRecipe(record.recipe),thumbnail:await blobURL(record.thumbnail)},'image-observer-template.json');say('已导出 JSON 备份。');
        })));
        c.append(actions);
      }
      return c;
    }
    let refreshRevision=0;
    async function refresh() {
      const revision=++refreshRevision,records=await transaction('readonly',store=>store.getAll());
      const nodes=await Promise.all(records.sort((a,b)=>b.created-a.created).map(r=>card(r)));
      if(revision!==refreshRevision)return;personal.replaceChildren(...nodes);
      if(!nodes.length){const p=document.createElement('p');p.textContent='尚未保存模板。';personal.append(p);}
    }
    const id=()=>crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random().toString(36).slice(2)}`;
    save.onclick=act(async()=>{
      if(save.disabled)return;save.disabled=true;
      try {
        const canvas=api.thumbnail(),recipe=validateRecipe(api.capture()),blob=await thumbnail(canvas);
        const name=prompt('模板名称（最多40个字符）','我的效果');if(name===null)return;
        await transaction('readwrite',store=>store.put({id:id(),name:nameOf(name),recipe,thumbnail:blob,created:Date.now()}));
        await refresh();say('已保存到当前浏览器。建议导出 JSON 备份。');
      } finally {save.disabled=false;}
    });
    importButton.onclick=()=>{file.value='';file.click();};
    file.onchange=act(async()=>{
      const input=file.files[0];if(!input)return;if(input.size>240000)throw new Error('模板 JSON 文件过大。');
      let data;try{data=JSON.parse(await input.text());}catch(_){throw new Error('无法解析模板 JSON。');}
      if(!plain(data)||data.format!==FORMAT||data.version!==VERSION)throw new Error('模板文件格式或版本不支持。');
      const name=nameOf(data.name),recipe=validateRecipe(data.recipe),blob=await validateThumbnail(data.thumbnail);
      await transaction('readwrite',store=>store.put({id:id(),name,recipe,thumbnail:blob,created:Date.now()}));await refresh();say('已导入模板。点击缩略图应用到当前图片。');
    });
    async function loadOfficial() {
      const config=window.ObserverOfficialPresets;
      if(!config||config.version!==1||!Array.isArray(config.slots)||config.slots.length!==4)throw new Error('官方预设配置格式不正确。');
      for(const entry of config.slots) {
        if(!entry)continue;
        const name=nameOf(entry.name),recipe=validateRecipe(entry.recipe),url=new URL(entry.thumbnail,location.href);
        if(url.origin!==location.origin||!url.pathname.startsWith(new URL('.',location.href).pathname)||!(/\.(jpg|jpeg|png|webp)$/i.test(url.pathname)))throw new Error('官方缩略图须为本站静态图片。');
        official.append(await card({name,recipe,thumbnail:url.href},true));
      }
      if(!official.children.length){const p=document.createElement('p');p.textContent='四个官方预设位已预留，等待你提供确认的图片和参数。';official.append(p);}
    }
    loadOfficial().catch(error=>say(error.message,true));
    refresh().catch(error=>say(`本地模板存储不可用：${error.message}。保存与导入不会显示为成功。`,true));
    return Object.freeze({validateRecipe});
  }
  return Object.freeze({init});
})();
