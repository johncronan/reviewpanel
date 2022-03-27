
function show(ref_id, item_id) {
  let id = "itemref_" + ref_id + "_" + item_id;
  let itemref = document.getElementById(id);
  let section = itemref.parentElement;
  section.querySelectorAll('.item-reference')
         .forEach(r => {
    if (r.dataset.ref == ref_id) r.style.display = 'none';
  });
  itemref.style.display = 'flex';
}

function selectorClick(event) {
  var item = event.target;
  if (item.tagName.toLowerCase() == 'img') item = item.parentElement;
  selector = item.parentElement;
  
  let refs = selector.dataset.refs.split(' ');
  for (let i=0; i < refs.length; i++) show(refs[i], item.dataset.id);
}

document.querySelectorAll('.item-thumbnail')
        .forEach(thumb => thumb.onclick = selectorClick);
