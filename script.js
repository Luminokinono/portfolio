(()=>{
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const slides=[...document.querySelectorAll('.swiper-slide')];let current=0,timer;
slides.forEach(slide=>{slide.style.setProperty('--slide-bg',slide.style.backgroundImage)});
const meter=document.createElement('div');meter.className='slide-meter';meter.setAttribute('aria-label','Choisir une diapositive');
const buttons=slides.map((_,index)=>{const b=document.createElement('button');b.type='button';b.setAttribute('aria-label',`Diapositive ${index+1}`);b.addEventListener('click',()=>{show(index);restart()});meter.append(b);return b});document.querySelector('header').append(meter);
function show(index){current=index;slides.forEach((slide,i)=>{slide.classList.toggle('current',i===index);slide.setAttribute('aria-hidden',String(i!==index));slide.querySelectorAll('a').forEach(a=>a.tabIndex=i===index?0:-1);buttons[i].classList.toggle('active',i===index);buttons[i].setAttribute('aria-pressed',String(i===index))})}
function restart(){clearInterval(timer);if(!reduced&&!document.hidden)timer=setInterval(()=>show((current+1)%slides.length),6500)}show(0);restart();document.addEventListener('visibilitychange',restart);document.querySelector('header').addEventListener('focusin',()=>clearInterval(timer));document.querySelector('header').addEventListener('focusout',restart);
// Charger et décoder les images avant de lancer la transition.
const preparedImages=['images/about.jpg','images/ma-photo.jpg'].map(src=>{
 const image=new Image();image.decoding='async';image.src=src;
 if(typeof image.decode==='function')image.decode().catch(()=>{});
 return image;
});
const about=document.getElementById('about-section'),home=document.getElementById('nav-home'),navAbout=document.getElementById('nav-about');about.inert=true;navAbout.setAttribute('aria-expanded','false');navAbout.setAttribute('aria-controls','about-section');
let closeTimer;
function finishClose(){if(about.classList.contains('active'))return;about.classList.remove('closing');document.body.style.overflow='';}
about.addEventListener('transitionend',event=>{if(event.target===about&&event.propertyName==='transform'){clearTimeout(closeTimer);finishClose()}});
function toggle(open){
 clearTimeout(closeTimer);
 if(open){about.classList.remove('closing');document.body.style.overflow='hidden';about.classList.add('active');}
 else if(about.classList.contains('active')){about.classList.add('closing');about.classList.remove('active');closeTimer=setTimeout(finishClose,reduced?0:850);}
 about.inert=!open;home.classList.toggle('active',!open);navAbout.classList.toggle('active',open);navAbout.setAttribute('aria-expanded',String(open));
}
navAbout.addEventListener('click',e=>{e.preventDefault();toggle(true)});home.addEventListener('click',e=>{e.preventDefault();toggle(false)});document.addEventListener('keydown',e=>{if(e.key==='Escape'){toggle(false);navAbout.focus()}});
const sections=[...document.querySelectorAll('header,#portfolio,#contact')],dots=[...document.querySelectorAll('.dot-nav .dot')];
const progress=document.createElement('div');progress.className='motion-progress';document.body.append(progress);let scheduled=false;
function update(){const max=document.documentElement.scrollHeight-innerHeight;progress.style.transform=`scaleX(${max>0?scrollY/max:0})`;let n=0;sections.forEach((s,i)=>{if(scrollY>=s.offsetTop-innerHeight/2)n=i});dots.forEach((d,i)=>d.classList.toggle('active',i===n));scheduled=false}
addEventListener('scroll',()=>{if(!scheduled){scheduled=true;requestAnimationFrame(update)}},{passive:true});addEventListener('resize',update);update();
if(!reduced&&'IntersectionObserver' in window){document.body.classList.add('motion-ready');const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');observer.unobserve(e.target)}}),{threshold:.1});document.querySelectorAll('#portfolio h2,.section-description,.gallery>a,.project-item,#contact h2,.contact-info,form').forEach((el,i)=>{el.classList.add('motion-reveal');el.style.transitionDelay=`${i%4*70}ms`;observer.observe(el)})}
if(!reduced&&matchMedia('(hover:hover) and (pointer:fine)').matches){document.querySelectorAll('.gallery>a,.project-item').forEach(card=>{card.addEventListener('pointermove',e=>{const b=card.getBoundingClientRect();card.style.transform=`perspective(900px) rotateX(${-(e.clientY-b.top-b.height/2)/b.height*5}deg) rotateY(${(e.clientX-b.left-b.width/2)/b.width*5}deg) translateY(-4px)`});card.addEventListener('pointerleave',()=>card.style.transform='')})}
})();
