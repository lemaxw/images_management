var currentIndex = 0; // Start at the first image
let events = [];  // Global or higher scope array to hold event data
let index = [];
let fuse;    
let currentPage = 1;
const itemsPerPage = 20;
let searchResults = []; // Global variable to store search results
let query = ""

document.addEventListener('DOMContentLoaded', function() {


    fetch('images.json')
        .then(response => response.json())
        .then(data => {
            currentIndex = 0;
            events = data;  // Store the fetched events in the higher scope array                    

            // Prefetch all text files
            const fetchTextPromises = events.map(event => {
                const descriptions = event.descriptions;
                const languages = ["ru", "ua", "en"];
                const textPromises = languages.map(lang => {
                    if (descriptions[lang]) {
                        const textUrl = descriptions[lang];
                        return fetch(textUrl)
                            .then(response => response.text())
                            .then(text => ({ lang, text }))
                            .catch(error => {
                                console.error(`Error fetching the description for ${lang}:`, error);
                                return null; // Return null in case of error
                            });
                    }
                });
                return Promise.all(textPromises).then(texts => {
                    event.texts = texts.reduce((acc, result) => {
                        if (result) { // Check if result is not null
                            const { lang, text } = result;

                            // Split the text by newline and extract the second-to-last element as the author
                            const lines = text.split('\n').filter(line => line.trim() !== '');
                            const author = lines[lines.length - 1]; // Get the n-1 element 
                            acc[lang] = { text, author }; // Include the author in the accumulator

                            //acc[lang] = text;
                        }
                        return acc;
                    }, {});
                });
            });

            // Once all text files are fetched, initialize the calendar
            Promise.all(fetchTextPromises).then(() => {
                var calendarEl = document.getElementById('calendar');
                var calendar = new FullCalendar.Calendar(calendarEl, {
                    initialView: 'dayGridMonth',
                    showNonCurrentDates: false,   // This hides the dates outside the current month
                    events: events.map((event, index) => ({
                        id: index, // Assign an ID to each event based on its array index
                        title: event.alt_ua, // or any other title logic
                        title_ru: event.alt_ru,
                        start: event.eventDate,
                        imageurl: event.thumb,
                        extendedProps: {
                            src: event.src,
                            descriptions: event.descriptions,
                            texts: event.texts
                        }
                    })),                 
                    eventContent: function(arg) {
                        let imageUrl = arg.event.extendedProps.imageurl;
                        let texts = arg.event.extendedProps.texts; // All text content
                        let languages = ["ru", "ua", "en"];
                        let currentIndexOfText = 0;

                        let element = document.createElement('div');
                        element.className = 'event-element';

                        let imageElement = document.createElement('img');
                        imageElement.src = imageUrl;
                        imageElement.className = 'event-image';
                        element.appendChild(imageElement); 

                        let textElement = document.createElement('div');                        
                        textElement.innerText = texts[languages[currentIndexOfText]];
                        textElement.className = 'event-text';
                        textElement.style.display = 'none';
                        element.appendChild(textElement);

                        element.addEventListener('mouseenter', function() {
                            currentIndexOfText = (currentIndexOfText + 1) % Object.keys(texts).length;
                            textElement.innerText = texts[languages[currentIndexOfText]].text;
                            textElement.style.display = 'block';
                        });

                        element.addEventListener('mouseleave', function() {
                            textElement.style.display = 'none';
                        });
                        
                        return { domNodes: [element] };
                    },
                    eventClick: function(info) {
                        currentIndex = parseInt(info.event.id, 10); // Get the id, which is the index in the array
                        const eventDetails = events[currentIndex]; // Use the index to retrieve full details
                        openEventPage(eventDetails);
                    },
                    eventDidMount: function(info) {
                        if (!info.isStart && !info.isEnd) { // Check if event is fully in another month
                            info.el.style.display = 'none'; 
                        }
                    }
                });
                calendar.render();
                buildIndex(events);
                // Initialize Fuse.js with the built index
                fuse = new Fuse(index, { keys: ['key'], threshold: 0.1 });  // Adjust threshold as needed    
            });
        })
        .catch(error => console.error('Error loading events:', error)); // Error handling for the fetch operation
    
   function getAuthorKey(textObj) { 
    if (textObj && textObj.author) {
        const segments = textObj.author .split('.') .map(word => word.trim()) .filter(word => word.length > 1); 
        return segments.length > 0 ? segments.pop() : null; } return null; 
    }
   /*
   // Build search index
   function buildIndex(images) {
        let totalImgKeys = [];
        images.forEach((image, idx) => {
            let imgKeys = [...image.tags.en, ...image.tags.ru, ...image.tags.ua];

            // Safely add alt texts if they exist
            if (image.alt_ru) imgKeys.push(...image.alt_ru.split(",").map(item => item.trim()));
            if (image.alt_ua) imgKeys.push(...image.alt_ua.split(",").map(item => item.trim()));
            if (image.alt_en) imgKeys.push(...image.alt_en.split(",").map(item => item.trim()));

            if (image.texts["ru"] && image.texts["ru"].author) imgKeys.push(image.texts["ru"].author.split('.').map(word => word.trim()).filter(word => word.length > 1).pop());
            if (image.texts["ua"] && image.texts["ua"].author) imgKeys.push(image.texts["ua"].author.split('.').map(word => word.trim()).filter(word => word.length > 1).pop());
            if (image.texts["en"] && image.texts["en"].author) imgKeys.push(image.texts["en"].author.split('.').map(word => word.trim()).filter(word => word.length > 1).pop());

            // Push each key with corresponding index into the array
            imgKeys.forEach(key => {
                index.push({ key: key.toLowerCase(), idx: idx });
            });
            totalImgKeys.push(...imgKeys);
        });   
        totalImgKeys = [...new Set(totalImgKeys)]
        new Awesomplete(searchInput, {maxItems: 20,  list: totalImgKeys });   
    }    
*/

    function buildIndex(images) {
        let totalImgKeys = [];
        images.forEach((image, idx) => {
            let imgKeys = [...image.tags.en, ...image.tags.ru, ...image.tags.ua];

            // Safely add alt texts if they exist
            if (image.alt_ru) {
                imgKeys.push(...image.alt_ru.split(",").map(item => item.trim()));
            }
            if (image.alt_ua) {
                imgKeys.push(...image.alt_ua.split(",").map(item => item.trim()));
            }
            if (image.alt_en) {
                imgKeys.push(...image.alt_en.split(",").map(item => item.trim()));
            }

            // Extract and add author keys, only if they are valid strings
            const ruAuthorKey = getAuthorKey(image.texts["ru"]);
            const uaAuthorKey = getAuthorKey(image.texts["ua"]);
            const enAuthorKey = getAuthorKey(image.texts["en"]);

            if (ruAuthorKey) imgKeys.push(ruAuthorKey);
            if (uaAuthorKey) imgKeys.push(uaAuthorKey);
            if (enAuthorKey) imgKeys.push(enAuthorKey);

            // Push each key into the index, guarding against empty/undefined values
            imgKeys.forEach(key => {
                if (typeof key === 'string' && key.trim().length > 0) {
                    index.push({ key: key.toLowerCase(), idx: idx });
                }
            });

            totalImgKeys.push(...imgKeys);
        });

        totalImgKeys = [...new Set(totalImgKeys)];
        new Awesomplete(searchInput, { maxItems: 20, list: totalImgKeys }); 
    }

    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('awesomplete-selectcomplete', () => {
        query = searchInput.value;        
        if (query) {            
            searchImages();
        }
        searchInput.value = ""
    });

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
                if(modal.style.display === 'none') {
                    document.getElementById('search-results-modal').style.display = 'none';
                    searchResults = [];
                }
                else {
                    modal.style.display = 'none';
                }
            } else {
                togglePoemTable();
            }
        } else if(event.key === "ArrowLeft" || event.key === "ArrowRight") {
            navigateImages(event.key);
        }
    });

     // Search and display results
     function searchImages() {
        let result = fuse.search(query.toLowerCase());

        searchResults = result.map(item => item.item.idx); // Store results globally
        searchResults = [...new Set(searchResults)]; // Remove duplicates

        if (searchResults.length > 0) {
            // Sort searchResults by eventDate before displaying them
            searchResults.sort((a, b) => {
                let dateA = new Date(events[a].eventDate);
                let dateB = new Date(events[b].eventDate);
                return dateA - dateB;  // Sort in ascending order
            });            
            displaySearchResults(1);
        } else {
            alert("No results found.");
        }
    }

    // Display search results with pagination
    function displaySearchResults(page) {
        currentPage = page;
        let startIdx = (currentPage - 1) * itemsPerPage;
        let endIdx = startIdx + itemsPerPage;
        let paginatedIndices = searchResults.slice(startIdx, endIdx);

        const resultsTitle = document.getElementById('results-title');
        resultsTitle.textContent = query;

        let grid = document.getElementById('thumbnail-grid');
        grid.innerHTML = '';  // Clear previous results
        let currInd = startIdx;

        paginatedIndices.forEach(idx => {
            let image = events[idx];
            let thumbDiv = document.createElement('div');
            thumbDiv.classList.add('thumbnail');

            let header = document.createElement('h3');
            header.innerText = image.eventDate;

            let thumb = document.createElement('img');
            thumb.src = image.thumb;
            thumb.alt = image.alt_en || "Image";
            thumb.addEventListener('click', () => {
                currentIndex = currInd++;
                openEventPage(image);                
            });

            thumbDiv.appendChild(header);
            thumbDiv.appendChild(thumb);
            grid.appendChild(thumbDiv);
        });

        // Manage the state of the pagination buttons
        let leftButton = document.getElementById('left-btn-search');
        let rightButton = document.getElementById('right-btn-search');

        // Enable or disable buttons, but keep them visible
        if (currentPage <= 1) {
            leftButton.disabled = true;
        } else {
            leftButton.disabled = false;
        }

        if (endIdx >= searchResults.length) {
            rightButton.disabled = true;
        } else {
            rightButton.disabled = false;
        }

        // Show the search results modal
        document.getElementById('search-results-modal').style.display = 'flex';
    }

    // Navigation buttons for pagination
    document.getElementById('left-btn-search').addEventListener('click', function () {
        if (currentPage > 1) {
            displaySearchResults(currentPage - 1);
        }
    });

    document.getElementById('right-btn-search').addEventListener('click', function () {
        if ((currentPage - 1) * itemsPerPage < searchResults.length) {
            displaySearchResults(currentPage + 1);
        }
    });

    // Close search results modal
    document.getElementById('close-btn-search').addEventListener('click', function () {
        document.getElementById('search-results-modal').style.display = 'none';
        searchResults = [];
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
        let activeArray = searchResults.length > 0 ? searchResults : events; // Use searchResults if available, otherwise fall back to events
    
        if (modal.style.display === 'flex') {
            if (direction === 'ArrowLeft') {
                if (currentIndex > 0) {
                    currentIndex -= 1; // Decrement index to show previous event        
                } else {
                    currentIndex = activeArray.length - 1; // Wrap around to the last event
                }
            } else if (direction === 'ArrowRight') {
                if (currentIndex < activeArray.length - 1) {
                    currentIndex += 1; // Increment index to show next event        
                } else {
                    currentIndex = 0; // Wrap around to the first event
                }
            }
            
                // If we are using searchResults, retrieve the correct event object using the index from searchResults
            let eventToOpen = searchResults.length > 0 ? events[activeArray[currentIndex]] : activeArray[currentIndex];

            // Open the event page with the selected event object
            openEventPage(eventToOpen);
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

   /*  // Toggle settings menu
    document.getElementById('settings-btn').addEventListener('click', function() {
        var menu = document.getElementById('settings-menu');
        if (menu.style.display === 'none' || menu.style.display === '') {
            menu.style.display = 'block';
        } else {
            menu.style.display = 'none';
        }
    }); */