// Portfolio Oumid Bilal : lumière, typographie variable et carrousel 3D.
(()=>{
const root=document.documentElement;
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const fine=matchMedia('(hover:hover) and (pointer:fine)').matches;
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const lerp=(a,b,t)=>a+(b-a)*t,clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const jump=y=>scrollTo({top:y,behavior:'instant'});
root.classList.add('js');if(!reduced)root.classList.add('motion');

// Pointeur partagé par toutes les animations ; sur écran tactile, une lumière se promène toute seule.
const pointer={x:innerWidth*.35,y:innerHeight*.45,sx:innerWidth*.35,sy:innerHeight*.45,moved:false};
addEventListener('pointermove',e=>{if(e.pointerType==='mouse'||e.pointerType==='pen'){pointer.x=e.clientX;pointer.y=e.clientY;pointer.moved=true}},{passive:true});

// ---------- Lettres du nom : graisse et remplissage selon la distance à la lumière ----------
$$('.hero-line').forEach(line=>{
  const text=line.textContent.trim();line.textContent='';
  [...text].forEach((c,i)=>{const s=document.createElement('span');s.className='ch';s.setAttribute('aria-hidden','true');s.textContent=c;s.style.setProperty('--i',i);line.append(s)});
});
const letters=$$('.ch');

// Ajuste la taille des titres pour que le plus long tienne en graisse maximale.
const heroName=$('.hero-name'),heroLines=$$('.hero-line');
function fitName(){
  heroLines.forEach(l=>l.style.fontSize='');
  const prev=letters.map(l=>l.style.fontWeight);letters.forEach(l=>l.style.fontWeight=700);
  const avail=heroName.clientWidth,widest=Math.max(...heroLines.map(line=>[...line.children].reduce((w,c)=>w+c.getBoundingClientRect().width,0)));
  const size=parseFloat(getComputedStyle(heroLines[0]).fontSize);
  if(widest>avail)heroLines.forEach(l=>l.style.fontSize=`${size*avail/widest*.98}px`);
  letters.forEach((l,i)=>l.style.fontWeight=prev[i]);
}
fitName();addEventListener('resize',fitName);if(document.fonts)document.fonts.ready.then(fitName);

// ---------- Diaporama de l'accueil : Bonjour, Welcome, Allez-y ----------
const slides=$$('.slide'),bars=$$('.hero-bars button'),barsBox=$('.hero-bars'),countEl=$('.hero-count strong');
const SLIDE_TIME=6500;let slideIndex=-1,slideTimer=null,flash=0;
function showSlide(n){
  if(n===slideIndex)return;
  const prev=slides[slideIndex];
  if(prev){prev.classList.remove('is-active');prev.classList.add('is-leaving');setTimeout(()=>prev.classList.remove('is-leaving'),1100)}
  slideIndex=n;const next=slides[n];next.classList.remove('is-leaving');void next.offsetWidth;next.classList.add('is-active');
  slides.forEach((s,i)=>s.setAttribute('aria-hidden',String(i!==n)));
  bars.forEach((b,i)=>{b.classList.remove('active');b.classList.toggle('done',i<n);b.setAttribute('aria-pressed',String(i===n))});
  void bars[n].offsetWidth;bars[n].classList.add('active');
  countEl.textContent=String(n+1).padStart(2,'0');
  if(prev)flash=1;
}
function startSlides(){clearInterval(slideTimer);if(reduced)return;slideTimer=setInterval(()=>{if(!document.hidden&&heroVisible)showSlide((slideIndex+1)%slides.length)},SLIDE_TIME)}
bars.forEach((b,i)=>b.addEventListener('click',()=>{showSlide(i);startSlides()}));
root.style.setProperty('--slide-time',`${SLIDE_TIME}ms`);

// ---------- Allumage ----------
let power=reduced?1:0;          // luminosité de la scène (0 à 1)
const loader=$('.loader'),count=$('.loader-count'),loaderBar=$('.loader-bar i');
function boot(){
  if(reduced||!loader){root.classList.add('ready');showSlide(0);startSlides();return}
  const images=$$('img').slice(0,6);let done=0;
  images.forEach(img=>{if(img.complete)done++;else img.addEventListener('load',()=>done++,{once:true}),img.addEventListener('error',()=>done++,{once:true})});
  const t0=performance.now();let shown=0,finished=false,last=t0;
  const finish=()=>{
    if(finished)return;finished=true;root.classList.add('ready');showSlide(0);startSlides();
    // Le néon s'allume en grésillant.
    const steps=[[0,0],[90,.7],[160,.08],[260,.9],[330,.25],[520,1]];const s0=performance.now();
    (function flick(now){const t=now-s0;let v=1;for(let i=steps.length-1;i>=0;i--){if(t>=steps[i][0]){v=steps[i][1];break}}power=v;if(t<560)requestAnimationFrame(flick);else power=1})(s0);
  };
  (function tick(now){
    if(finished)return;
    const t=now-t0,target=t>4500?100:Math.min(100,Math.min(t/1500,1)*55+done/images.length*45);
    // Avance au rythme du temps réel, pas du nombre d'images par seconde.
    const dt=now-last;last=now;shown=lerp(shown,target,Math.min(1,dt/140));if(target>=100&&t>1400)shown=Math.max(shown,99.6);if(shown>99.5)shown=100;
    count.textContent=String(Math.round(shown)).padStart(3,'0');loaderBar.style.transform=`scaleX(${shown/100})`;
    if(shown>=100&&t>1400)finish();else requestAnimationFrame(tick);
  })(t0);
  setTimeout(finish,7000);
}
boot();

// ---------- Shader : filaments de lumière qui ondulent et se courbent autour du curseur ----------
const canvas=$('.hero-light'),hero=$('.hero');
const gl=canvas&&canvas.getContext('webgl',{antialias:false,alpha:false,powerPreference:'high-performance'});
let heroVisible=true,drawLight=()=>{};
if(gl){
  const vs='attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const fs=`precision highp float;
  uniform vec2 r;uniform float t;uniform vec2 m;uniform float on;uniform float sc;
  float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
  float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}
  float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*n(p);p*=2.02;a*=.5;}return v;}
  void main(){
    vec2 uv=(gl_FragCoord.xy-.5*r)/r.y;vec2 mo=(m-.5*r)/r.y;
    vec2 d=uv-mo;float dl=length(d);
    uv-=d*.22*exp(-dl*3.5);                    // lentille autour du curseur
    vec3 col=vec3(0.);
    for(int i=0;i<7;i++){
      float fi=float(i);
      float y=uv.y+.28*sin(uv.x*1.3+t*.25+fi*1.9)+.22*(fbm(vec2(uv.x*.9+t*.04,fi*3.1))-.5)-(fi-3.)*.085;
      y+=.12*sin(uv.x*3.+t*.6+fi)*exp(-dl*2.);   // agitation près de la lumière
      float w=.0016+.0009*fi;
      float glow=w/abs(y)+w*.18/(y*y+.0004)*.02;
      vec3 c=mix(vec3(.31,.49,1.),vec3(.76,.35,.84),fi/6.);
      col+=c*glow*(.55+.45*sin(uv.x*2.+t*.8+fi*2.));
    }
    col+=vec3(.76,.35,.84)*.022/(dl*dl+.035);   // halo du curseur
    col*=on*(1.-sc*.85);
    col*=1.-.55*dot(uv*.7,uv*.7);              // vignette
    col=1.-exp(-col*1.25);
    col+=(h(gl_FragCoord.xy+t)-.5)*.015;
    gl_FragColor=vec4(col,1.);
  }`;
  const sh=(type,src)=>{const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);return s};
  const pr=gl.createProgram();gl.attachShader(pr,sh(gl.VERTEX_SHADER,vs));gl.attachShader(pr,sh(gl.FRAGMENT_SHADER,fs));gl.linkProgram(pr);
  if(gl.getProgramParameter(pr,gl.LINK_STATUS)){
    gl.useProgram(pr);
    const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
    const loc=gl.getAttribLocation(pr,'p');gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,2,gl.FLOAT,false,0,0);
    const u={r:gl.getUniformLocation(pr,'r'),t:gl.getUniformLocation(pr,'t'),m:gl.getUniformLocation(pr,'m'),on:gl.getUniformLocation(pr,'on'),sc:gl.getUniformLocation(pr,'sc')};
    let dpr=1;
    const size=()=>{dpr=Math.min(devicePixelRatio||1,innerWidth<700?1.25:1.5);canvas.width=hero.clientWidth*dpr;canvas.height=hero.clientHeight*dpr;gl.viewport(0,0,canvas.width,canvas.height)};
    size();addEventListener('resize',size);
    new IntersectionObserver(([e])=>heroVisible=e.isIntersecting).observe(hero);
    const start=performance.now();
    drawLight=(lx,ly,scroll)=>{
      gl.uniform2f(u.r,canvas.width,canvas.height);gl.uniform1f(u.t,reduced?8:(performance.now()-start)/1000);
      gl.uniform2f(u.m,lx*dpr,canvas.height-ly*dpr);gl.uniform1f(u.on,power*(1+flash*.7));gl.uniform1f(u.sc,scroll);
      gl.drawArrays(gl.TRIANGLES,0,3);
    };
    $('.hero-fallback').style.display='none';
  }
}

// ---------- Texte « À propos » : les mots s'allument au fil du scroll ----------
const manifesto=$('.manifesto');
const words=[];
if(manifesto){
  const text=manifesto.textContent.trim().replace(/\s+/g,' ');manifesto.textContent='';
  text.split(' ').forEach((w,i,a)=>{const s=document.createElement('span');s.className='w';s.textContent=w;manifesto.append(s);if(i<a.length-1)manifesto.append(' ');words.push(s)});
}
const photo=$('.about-photo');
if(photo&&fine&&!reduced){
  photo.addEventListener('pointermove',e=>{const b=photo.getBoundingClientRect();photo._x=(e.clientX-b.left)/b.width*100;photo._y=(e.clientY-b.top)/b.height*100});
  photo.addEventListener('pointerleave',()=>{photo._x=null});
}

// ---------- Titres découpés par mot ----------
$$('.work-title,.contact-title span,.contact-title em').forEach(el=>{
  const text=el.textContent.trim();el.setAttribute('aria-label',text);el.textContent='';el.classList.add('split');
  text.split(' ').forEach((w,i)=>{const m=document.createElement('span');m.className='wm';m.setAttribute('aria-hidden','true');const s=document.createElement('span');s.textContent=w;s.style.setProperty('--i',i);m.append(s);el.append(m,' ')});
});
$$('.eyebrow,.facts,.about-actions,.contact-list,.contact-form,.about-photo').forEach(el=>el.classList.add('reveal'));
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}}),{threshold:.15,rootMargin:'0px 0px -5% 0px'});
$$('.reveal,.split').forEach(el=>io.observe(el));
// Filet de sécurité : rien ne reste caché si l'observer ne se déclenche pas.
setTimeout(()=>$$('.reveal,.split').forEach(el=>{const b=el.getBoundingClientRect();if(b.top<innerHeight)el.classList.add('in')}),4000);

// ---------- Projets : section figée, carrousel 3D piloté par le scroll ----------
const work=$('.work'),sticky=$('.work-sticky'),track=$('.work-track'),cards=$$('.card'),ghost=$('.work-ghost');
const current=$('.work-current'),workBar=$('.work-bar i');
let maxX=0,workTop=0,wx=0,lastWx=0;
const measure=()=>{
  if(reduced){work.style.height='';return}
  maxX=Math.max(0,track.scrollWidth-innerWidth);work.style.height=`${innerHeight+maxX}px`;workTop=work.getBoundingClientRect().top+scrollY;
};
measure();addEventListener('resize',measure);addEventListener('load',measure);
if(document.fonts)document.fonts.ready.then(measure);
cards.forEach(card=>{
  card._t={x:0,y:0,tx:0,ty:0};
  if(!fine)return;
  card.addEventListener('pointermove',e=>{const b=card.getBoundingClientRect();card._t.tx=((e.clientX-b.left)/b.width-.5)*14;card._t.ty=-((e.clientY-b.top)/b.height-.5)*10});
  card.addEventListener('pointerleave',()=>{card._t.tx=0;card._t.ty=0});
});
if(!reduced){
  let dragging=false,startX=0,startY=0,moved=0;
  sticky.addEventListener('pointerdown',e=>{if(e.button!==0)return;dragging=true;startX=e.clientX;startY=scrollY;moved=0});
  addEventListener('pointermove',e=>{if(!dragging)return;const dx=e.clientX-startX;moved=Math.max(moved,Math.abs(dx));if(moved>5){track.classList.add('dragging');jump(startY-dx*1.4)}},{passive:true});
  const stop=()=>{dragging=false;track.classList.remove('dragging')};
  addEventListener('pointerup',stop);addEventListener('pointercancel',stop);
  sticky.addEventListener('click',e=>{if(moved>8){e.preventDefault();e.stopPropagation()}},true);
  work.addEventListener('wheel',e=>{if(Math.abs(e.deltaX)>Math.abs(e.deltaY)){const r=work.getBoundingClientRect();if(r.top<=1&&r.bottom>=innerHeight-1){e.preventDefault();jump(scrollY+e.deltaX)}}},{passive:false});
  track.addEventListener('focusin',e=>{const item=e.target.closest('.work-track>*');if(!item)return;sticky.scrollLeft=0;jump(workTop+clamp(item.offsetLeft+item.offsetWidth/2-innerWidth/2,0,maxX))});
}

// ---------- Bandeau : vitesse et sens suivent le scroll ----------
const band=$('.band-track');let bx=0,bandVisible=false;
new IntersectionObserver(([e])=>bandVisible=e.isIntersecting).observe($('.band'));

// ---------- Boucle principale ----------
const navBar=$('.nav-progress i'),navLinks=$$('.nav-links a');
const sections=['about','work','contact'].map(id=>document.getElementById(id));
let lastY=scrollY,vel=0,dir=-1,auto=0;
function frame(now){
  const y=scrollY,dy=y-lastY;lastY=y;vel=lerp(vel,dy,.1);if(Math.abs(dy)>.5)dir=dy>0?-1:1;
  const docMax=document.documentElement.scrollHeight-innerHeight;
  navBar.style.transform=`scaleX(${docMax>0?y/docMax:0})`;
  let active=-1;sections.forEach((s,i)=>{if(s.getBoundingClientRect().top<innerHeight*.5)active=i});
  navLinks.forEach((a,i)=>a.classList.toggle('active',i===active));

  // Source de lumière : la souris, ou une trajectoire automatique sur tactile.
  if(!pointer.moved){auto+=reduced?0:.006;pointer.x=innerWidth*(.5+.32*Math.sin(auto*1.3));pointer.y=innerHeight*(.45+.22*Math.sin(auto*2.1+1))}
  pointer.sx=lerp(pointer.sx,pointer.x,.09);pointer.sy=lerp(pointer.sy,pointer.y,.09);

  // Hero
  const heroRect=hero.getBoundingClientRect(),heroP=clamp(-heroRect.top/heroRect.height,0,1);
  if(heroVisible){
    drawLight(pointer.sx,pointer.sy-heroRect.top,heroP);
    const ly=pointer.sy;
    flash=lerp(flash,0,.04);
    $$('.ch',slides[Math.max(slideIndex,0)]).forEach(l=>{
      const b=l.getBoundingClientRect(),cx=b.left+b.width/2,cy=b.top+b.height/2;
      const k=reduced?1:Math.exp(-(((cx-pointer.sx)**2+(cy-ly)**2)/(innerWidth*innerWidth*.035)))*power;
      const kk=lerp(l._k||0,k,.12);l._k=kk;
      l.style.fontWeight=Math.round(200+500*kk);l.style.setProperty('--fill',kk.toFixed(3));
    });
  }

  // À propos : mots + lampe torche sur la photo
  if(manifesto){
    const r=manifesto.getBoundingClientRect(),p=clamp((innerHeight*.82-r.top)/(r.height+innerHeight*.15),0,1);
    const lit=p*(words.length+4);
    words.forEach((w,i)=>{const v=reduced?1:clamp(lit-i,0,1);w.style.opacity=(.16+.84*v).toFixed(3)});
  }
  if(photo&&!reduced){
    const r=photo.getBoundingClientRect(),p=clamp((innerHeight-r.top)/(innerHeight+r.height*.4),0,1);
    const tx=photo._x!=null?photo._x:40,ty=photo._x!=null?photo._y:36;
    photo._sx=lerp(photo._sx??40,tx,.1);photo._sy=lerp(photo._sy??36,ty,.1);
    photo.style.setProperty('--x',`${photo._sx}%`);photo.style.setProperty('--y',`${photo._sy}%`);
    photo.style.setProperty('--r',`${(photo._x!=null?44:12+p*46)}%`);
  }

  // Carrousel 3D
  const wr=work.getBoundingClientRect();
  if(!reduced&&wr.bottom>-50&&wr.top<innerHeight+50){
    const p=maxX?clamp(-wr.top/maxX,0,1):0;wx=lerp(wx,-p*maxX,.1);if(Math.abs(wx+p*maxX)<.05)wx=-p*maxX;
    const v=wx-lastWx;lastWx=wx;
    track.style.transform=`translate3d(${wx}px,0,0)`;ghost.style.transform=`translate3d(${wx*.3}px,0,0)`;workBar.style.transform=`scaleX(${p})`;
    const lean=clamp(v*.2,-14,14);let best=0,bestD=Infinity;
    cards.forEach((card,i)=>{
      const off=(card.offsetLeft+card.offsetWidth/2+wx-innerWidth/2)/Math.max(innerWidth,1000),d=Math.abs(off),t=card._t;
      t.x=lerp(t.x,t.tx,.12);t.y=lerp(t.y,t.ty,.12);
      card.style.transform=`translate3d(0,${d*d*40}px,${-Math.pow(d,1.25)*420}px) rotateY(${clamp(off*48,-58,58)+lean+t.x}deg) rotateX(${t.y}deg)`;
      card.style.setProperty('--depth',Math.min(.7,d*.65).toFixed(3));
      const img=card.querySelector('img');img.style.translate=`${off*-9}% 0`;
      if(d<bestD){bestD=d;best=i}
      if(card.offsetLeft+wx<innerWidth*.95)card.classList.add('in');
    });
    current.textContent=String(best+1).padStart(2,'0');
    if(fine)sticky.style.perspectiveOrigin=`${50+(pointer.sx/innerWidth-.5)*16}% ${50+(pointer.sy/innerHeight-.5)*16}%`;
  }

  // Bandeau
  if(bandVisible&&!reduced){
    const w=band.scrollWidth/2;bx+=dir*(.8+Math.min(Math.abs(vel),60)*.35);if(bx<=-w)bx+=w;if(bx>0)bx-=w;
    band.style.transform=`translate3d(${bx}px,0,0) skewX(${clamp(-vel*.3,-10,10)}deg)`;
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// ---------- Copier l'email ----------
$$('.copy').forEach(btn=>btn.addEventListener('click',()=>{
  const value=btn.dataset.copy,ok=()=>{btn.textContent='Copi\u00e9';btn.classList.add('done');setTimeout(()=>{btn.textContent='Copier';btn.classList.remove('done')},1800)};
  if(navigator.clipboard)navigator.clipboard.writeText(value).then(ok,()=>select());else select();
  function select(){const r=document.createRange();r.selectNodeContents($('.email-text'));const s=getSelection();s.removeAllRanges();s.addRange(r)}
}));

// ---------- Horloge Île-de-France ----------
const clock=$('.clock');
const tickClock=()=>{clock.textContent=new Intl.DateTimeFormat('fr-FR',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Paris'}).format(new Date())};
tickClock();setInterval(tickClock,30000);

// ---------- Grain ----------
if(!reduced){
  const c=document.createElement('canvas');c.width=c.height=160;const x=c.getContext('2d'),img=x.createImageData(160,160);
  for(let i=0;i<img.data.length;i+=4){const v=Math.random()*255|0;img.data[i]=img.data[i+1]=img.data[i+2]=v;img.data[i+3]=255}
  x.putImageData(img,0,0);$('.grain').style.backgroundImage=`url(${c.toDataURL()})`;
}

if(!fine||reduced)return;

// ---------- Curseur lumière ----------
document.body.classList.add('has-cursor');
const glow=document.createElement('div'),dot=document.createElement('div');glow.className='cursor-glow';dot.className='cursor-dot';
glow.append(document.createElement('b'));const shape=document.createElement('b'),label=document.createElement('em');shape.append(label);dot.append(shape);
[glow,dot].forEach(el=>{el.setAttribute('aria-hidden','true');document.body.append(el)});
let gx=pointer.x,gy=pointer.y;
addEventListener('pointermove',e=>{dot.style.transform=`translate(${e.clientX}px,${e.clientY}px)`;document.body.classList.add('cursor-on')},{passive:true});
root.addEventListener('pointerleave',()=>document.body.classList.remove('cursor-on'));
(function follow(){gx=lerp(gx,pointer.x,.12);gy=lerp(gy,pointer.y,.12);glow.style.transform=`translate(${gx}px,${gy}px)`;requestAnimationFrame(follow)})();
document.addEventListener('pointerover',e=>{
  // Sur les icônes, le curseur reste un petit point pour laisser voir leur animation.
  if(e.target.closest('.ic')){dot.classList.remove('is-field','is-label','is-link');return}
  const el=e.target.closest('[data-cursor],a,button'),field=e.target.closest('input,textarea'),inTrack=e.target.closest('.work-sticky');
  const text=el?.dataset.cursor||(!el&&inTrack&&!field?'Glisser':'');
  dot.classList.toggle('is-field',!!field);dot.classList.toggle('is-label',!!text&&!field);dot.classList.toggle('is-link',!!el&&!text);
  if(text)label.textContent=text;
});

// ---------- Boutons magnétiques ----------
$$('[data-magnetic]').forEach(el=>{
  const base=getComputedStyle(el).transition;
  el.style.transition=`${base&&!base.startsWith('all 0s')?base+', ':''}translate .7s cubic-bezier(.16,1,.3,1)`;
  el.addEventListener('pointermove',e=>{const b=el.getBoundingClientRect();el.style.translate=`${(e.clientX-b.left-b.width/2)*.3}px ${(e.clientY-b.top-b.height/2)*.35}px`});
  el.addEventListener('pointerleave',()=>el.style.translate='');
});
})();
