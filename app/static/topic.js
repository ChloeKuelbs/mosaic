'use strict';
const slug = location.pathname.split('/').filter(Boolean).pop();
window.mosaicTopic = slug;
const $topic = id => document.getElementById(id);
async function initTopic() {
  try {
    const res=await fetch('/api/topics/'+encodeURIComponent(slug));
    if(!res.ok) throw new Error('Topic unavailable');
    const topic=await res.json();
    document.title=topic.name+' · Mosaic';
    const intro=document.querySelector('.intro');
    intro.querySelector('.eyebrow').textContent='THE EVIDENCE EXPLORER / '+topic.category.toUpperCase();
    intro.querySelector('h1').replaceChildren(document.createTextNode(topic.name));
    intro.querySelector('p').textContent=topic.short+'. Explore the latest indexed publications and registered clinical trials.';
    $topic('topic-scope').textContent=topic.name;
    document.querySelectorAll('[data-query]').forEach((b,i)=>{if(topic.examples[i]){b.dataset.query=topic.examples[i];b.textContent=topic.examples[i];}else b.hidden=true;});
    $topic('intervention').placeholder='e.g. '+topic.examples.slice(0,2).join(', ');
    $topic('literature-status').textContent='Loading recent publications from PubMed…';
    const response=await fetch('/api/topics/'+encodeURIComponent(slug)+'/literature');
    if(!response.ok) throw new Error('Recent publications could not be loaded. Please retry later.');
    const data=await response.json();
    const container=$topic('literature-results');
    container.replaceChildren();
    if(!data.items.length){$topic('literature-status').textContent='No recent publications returned for this search.';return;}
    data.items.forEach(item=>{
      const article=document.createElement('article');article.className='paper-card';
      const meta=document.createElement('span');meta.className='paper-meta';meta.textContent=[item.published,item.journal].filter(Boolean).join(' · ');
      const link=document.createElement('a');link.href=item.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.title+' ↗';
      const authors=document.createElement('p');authors.textContent=item.authors.join(', ');
      article.append(meta,link,authors);container.append(article);
    });
    $topic('literature-status').textContent=data.items.length+' recent PubMed-indexed publications · Retrieved '+new Date(data.retrieved_at).toLocaleDateString()+'.';
  }catch(err){$topic('literature-status').textContent=err.message;}
}
initTopic();
