var currentIndex = 0; // Start at the first image
let events = [];  // Global or higher scope array to hold event data

document.addEventListener('DOMContentLoaded', function() {
    fetch('images.json')
    .then(response => response.json())
    .then(data  => {
        currentIndex = 0;
        events = data;  // Store the fetched events in the higher scope array
        var calendarEl = document.getElementById('calendar');
        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',   
            events: events.map((event, index) => ({
                id: index, // Assign an ID to each event based on its array index
                title: event.alt_ua, // or any other title logic
                title_ru: event.alt_ru,
                start: event.eventDate,
                imageurl: event.thumb,
                extendedProps: {
                    src: event.src,
                    descriptions: event.descriptions
                }
            })),
            eventContent: function(arg) {
                let imageUrl = arg.event.extendedProps.imageurl;
                let element = document.createElement('div');
                
                element.style.width = '100%'; // Adjust this for image width
                element.style.height = '100%'; // Adjust this for image height
                if(imageUrl) {
                    let imageElement = document.createElement('img');
                    imageElement.src = imageUrl;
                    imageElement.style.width = '100%'; // Make sure the image fits the container
                    imageElement.style.height = 'auto'; // Maintain aspect ratio
                    element.appendChild(imageElement);                  
                }
                return { domNodes: [element] };
            },
            eventClick: function(info) {
                currentIndex =  parseInt(info.event.id, 10); // Get the id, which is the index in the array
                const eventDetails = events[currentIndex]; // Use the index to retrieve full details
                openEventPage(eventDetails);
            }
        });
        calendar.render();
    })
    .catch(error => console.error('Error loading events:', error)); // Error handling for the fetch operation

    // Close button functionality
    document.getElementById('close-btn').onclick = function() {
        document.getElementById('modal').style.display = 'none';
    }
    const poemTable = document.getElementById('poem-table');
    // Close modal by clicking outside the modal content
    document.getElementById('modal').addEventListener('click', function(event) {
        if (event.target === this) {            
            if (poemTable.style.display === 'none' || poemTable.style.display === '') {
                this.style.display = 'none';
            } else {
                togglePoemTable();
            }
        }
    });
    document.getElementById('left-btn').addEventListener('click', function() {
        navigateImages("ArrowLeft")
    });

    document.getElementById('right-btn').addEventListener('click', function() {
        navigateImages("ArrowRight")
    });

    document.getElementById('poem-btn').addEventListener('click', function() {
        togglePoemTable();
    });

    document.getElementById('modal-image').addEventListener('click', function() {
        togglePoemTable();
    });

    // Close modal on Escape key press
    document.addEventListener('keydown', function(event) {
        const modal = document.getElementById('modal');        
        if (event.key === "Escape") {
            if (poemTable.style.display === 'none' || poemTable.style.display === '') {
                modal.style.display = 'none';
            } else {
                togglePoemTable();
            }
        } else if(event.key === "ArrowLeft" || event.key === "ArrowRight") {
            navigateImages(event.key);
        }
    });


    function adjustLayout() {
        var img = document.getElementById('modal-image');
        var container = document.getElementById('image-and-text-container');
        var textContent = document.getElementById('text-content');

        if (img && container && textContent) {
            /*if (img.naturalWidth < img.naturalHeight) {
                container.style.flexDirection = 'row';
                textContent.style.flexDirection = 'column';
                textContent.classList.remove('column'); // Ensure text blocks stack vertically
            } else*/ {
                container.style.flexDirection = 'column';
                textContent.style.flexDirection = 'row';
                textContent.classList.add('column'); // Ensure text blocks form two columns
            }
        } else {
            console.error("One or more elements are missing for layout adjustment!");
        }
    }

function navigateImages(direction) {
    if (modal.style.display === 'flex') {
        if (direction === 'ArrowLeft') {
            if (currentIndex > 0) {
                currentIndex -= 1; // Decrement index to show previous event        
            } else {
                currentIndex = events.length - 1;
            }
        } else if (direction === 'ArrowRight') {
            if (currentIndex < events.length - 1) {
                currentIndex += 1; // Increment index to show next event        
            } else {
                currentIndex = 0;
            }
        }
        openEventPage(events[currentIndex]);
    }
}

function togglePoemTable() {
    const poemTable = document.getElementById('poem-table');
    if (poemTable.style.display === 'none' || poemTable.style.display === '') {
        poemTable.style.display = 'block';
    } else {
        poemTable.style.display = 'none';
    }
}

function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.src = url;
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error('Failed to load image.'));
    });
}

let texts = [];
let btnTexts = ["стихи", "вірші", "poems"];
let currentLangIndex = 0;
function changeText() {
    const modalTitle = document.getElementById('modal-title-ua');
    const poemBtn = document.getElementById('poem-btn');
    modalTitle.textContent = texts[currentLangIndex];
    poemBtn.textContent = btnTexts[currentLangIndex];
    currentLangIndex = (currentLangIndex + 1) % texts.length;
}

let timer = false;
function openEventPage(details) {
    const img = document.getElementById('modal-image');    
    const modalTitleDate = document.getElementById('modal-title-date');
    const modal = document.getElementById('modal');

    loadImage(details.src).then(loadedImg => {
        // Set image and modal title attributes
        img.src = loadedImg.src;
        texts = [];        
                
        
        modalTitleDate.textContent = details.eventDate;

    
        // Adjust layout when image loads
        img.onload = adjustLayout;
    
        // Set and fetch descriptions
        var i=0;        
        handleLinkAndDescription(details, texts, i++, 'ru');
        handleLinkAndDescription(details, texts, i++, 'ua');
        handleLinkAndDescription(details, texts, i++, 'en');
        currentLangIndex = 0;
        changeText();
        if (!timer) {
            setInterval(changeText, 10000);
            timer = true;
        }
        // Show the modal
        modal.style.display = 'flex';            
    }).catch(error => {
        alert(error.message);
    });


}

function handleLinkAndDescription(details, texts, i, lang) {
    const element = document.getElementById(`link-${lang}`);
    if (details.descriptions && details.descriptions[`${lang}_link`]) {
        element.href = details.descriptions[`${lang}_link`];
        element.style.display = '';
        texts[i] = details[`alt_${lang}`];
        fetchDescription(details.descriptions[lang], element);
    } else {
        element.style.display = 'none';
        return;
    }
}


function fetchDescription(url, element) {
    fetch(url)
        .then(response => response.text())
        .then(text => {
            element.innerText = text;
        })
        .catch(error => {
            console.error('Error fetching the description:', error);
        });
}

dragElement(document.getElementById("poem-table"));

function dragElement(elmnt) {
    var pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    elmnt.onmousedown = dragMouseDown;

    function dragMouseDown(e) {
        e = e || window.event;
        e.preventDefault();
        // Get the mouse cursor position at startup
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        // Call a function whenever the cursor moves
        document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
        e = e || window.event;
        e.preventDefault();
        // Calculate the new cursor position
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        // Set the element's new position
        elmnt.style.top = (elmnt.offsetTop - pos2) + "px";
        elmnt.style.left = (elmnt.offsetLeft - pos1) + "px";
    }

    function closeDragElement() {
        // Stop moving when mouse button is released
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

});