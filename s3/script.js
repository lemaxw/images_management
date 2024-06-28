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

    // Close modal by clicking outside the modal content
    document.getElementById('modal').addEventListener('click', function(event) {
        if (event.target === this) {
            this.style.display = 'none';
        }
    });
    document.getElementById('left-btn').addEventListener('click', function() {
        if (currentIndex > 0) {
            currentIndex -= 1; // Decrement index to show previous event        
        } else {
            currentIndex = events.length - 1;
        }
        openEventPage(events[currentIndex]);
    });

    document.getElementById('right-btn').addEventListener('click', function() {
        if (currentIndex < events.length - 1) {
            currentIndex += 1; // Increment index to show next event        
        } else {
            currentIndex = 0;
        }
        openEventPage(events[currentIndex]);
    });
    // Close modal on Escape key press
    document.addEventListener('keydown', function(event) {
        const modal = document.getElementById('modal');
        if (event.key === "Escape") {
            modal.style.display = 'none';
        }
    });


    function adjustLayout() {
    var img = document.getElementById('modal-image');
    var container = document.getElementById('image-and-text-container');
    var textContent = document.getElementById('text-content');

    if (img && container && textContent) {
        if (img.naturalWidth < img.naturalHeight) {
            container.style.flexDirection = 'row';
            textContent.style.flexDirection = 'column';
            textContent.classList.remove('column'); // Ensure text blocks stack vertically
        } else {
            container.style.flexDirection = 'column';
            textContent.style.flexDirection = 'row';
            textContent.classList.add('column'); // Ensure text blocks form two columns
        }
    } else {
        console.error("One or more elements are missing for layout adjustment!");
    }
}


function openEventPage(details) {
    const img = document.getElementById('modal-image');
    const modalTitleUa = document.getElementById('modal-title-ua');
    const modal = document.getElementById('modal');

    // Set image and modal title attributes
    img.src = details.src;
    img.alt = details.alt_ru;
    modalTitleUa.textContent = details.alt_ua;

    // Adjust layout when image loads
    img.onload = adjustLayout;

    // Set and fetch descriptions
    handleLinkAndDescription(details.descriptions, 'ru');
    handleLinkAndDescription(details.descriptions, 'ua');
    handleLinkAndDescription(details.descriptions, 'en');

    // Show the modal
    modal.style.display = 'flex';
}

function handleLinkAndDescription(descriptions, lang) {
    const element = document.getElementById(`link-${lang}`);
    if (descriptions && descriptions[`${lang}_link`]) {
        element.href = descriptions[`${lang}_link`];
        element.style.display = '';
    } else {
        element.style.display = 'none';
        return;
    }

    if (descriptions && descriptions[lang]) {
        fetchDescription(descriptions[lang], element);
    } else {
        element.style.display = 'none';
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
});