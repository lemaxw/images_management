var currentIndex = 0; // Start at the first image
let events = [];  // Global or higher scope array to hold event data
let index = [];
let fuse;    
let currentPage = 1;
const itemsPerPage = 20;
let searchResults = []; // Global variable to store search results
let query = ""
const poemCache = new Map();
let textLangs = [];

document.addEventListener('DOMContentLoaded', function() {


    fetch('images.json')
        .then(response => response.json())
        .then(data => {
            currentIndex = 0;
            events = data.map(event => ({ ...event, texts: event.texts || {} }));  // Store the fetched events in the higher scope array                    
            renderCalendar(events);
            buildIndex(events);
            // Initialize Fuse.js with the built index
            fuse = new Fuse(index, { keys: ['key'], threshold: 0.1 });  // Adjust threshold as needed    
        })
        .catch(error => console.error('Error loading events:', error)); // Error handling for the fetch operation
    
   function getAuthorKey(textObj) { 
    if (textObj && textObj.author) {
        const segments = textObj.author .split('.') .map(word => word.trim()) .filter(word => word.length > 1); 
        return segments.length > 0 ? segments.pop() : null; } return null; 
    }
   

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

    function renderCalendar(events) {
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
                    texts: event.texts,
                    titles: {
                        ru: event.alt_ru,
                        ua: event.alt_ua,
                        en: event.alt_en
                    }
                }
            })),                 
            eventContent: function(arg) {
                let imageUrl = arg.event.extendedProps.imageurl;
                let texts = arg.event.extendedProps.texts || {}; // All text content
                let titles = arg.event.extendedProps.titles || {};
                let languages = ["ru", "ua", "en"];
                let currentIndexOfText = 0;
                const eventData = events[arg.event.id];

                let element = document.createElement('div');
                element.className = 'event-element';

                let imageElement = document.createElement('img');
                imageElement.src = imageUrl;
                imageElement.className = 'event-image';
                imageElement.loading = 'lazy';
                imageElement.decoding = 'async';
                element.appendChild(imageElement); 

                let textElement = document.createElement('div');                        
                textElement.innerText = titles[languages[currentIndexOfText]] || '';
                textElement.className = 'event-text';
                textElement.style.display = 'none';
                element.appendChild(textElement);

                element.addEventListener('mouseenter', function() {
                    currentIndexOfText = (currentIndexOfText + 1) % languages.length;
                    let lang = languages[currentIndexOfText];
                    const showText = () => {
                        let textValue = (texts[lang] && texts[lang].text) || titles[lang] || '';
                        textElement.innerText = textValue;
                        textElement.style.display = 'block';
                    };
                    if (texts && Object.keys(texts).length) {
                        showText();
                    } else {
                        loadEventTexts(eventData).then(loaded => {
                            texts = loaded;
                            showText();
                        }).catch(() => {
                            showText();
                        });
                    }
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
            thumb.loading = 'lazy';
            thumb.decoding = 'async';
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
    let btnTexts = { ru: "стихи", ua: "вірші", en: "poems" };
    let currentLangIndex = 0;
    function changeText() {
        if (!texts.length || !textLangs.length) return;
        const modalTitle = document.getElementById('modal-title-ua');        
        const poemBtn = document.getElementById('poem-btn');
        modalTitle.textContent = texts[currentLangIndex];
        const lang = textLangs[currentLangIndex];
        poemBtn.textContent = btnTexts[lang] || "poems";
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
            textLangs = [];
                    
            
            modalTitleDate.textContent = details.eventDate;

        
            // Adjust layout when image loads
            img.onload = adjustLayout;
        
            // Set and fetch descriptions
            loadEventTexts(details).then(loadedTexts => {
                handleLinkAndDescription(details, texts, 'ru', loadedTexts);
                handleLinkAndDescription(details, texts, 'ua', loadedTexts);
                handleLinkAndDescription(details, texts, 'en', loadedTexts);
                currentLangIndex = 0;
                if (texts.length) {
                    changeText();
                    document.getElementById('poem-btn').style.display = '';
                    if (!timer) {
                        setInterval(changeText, 10000);
                        timer = true;
                    }
                } else {
                    document.getElementById('poem-btn').style.display = 'none';
                    const poemTable = document.getElementById('poem-table');
                    poemTable.style.display = 'none';
                }
                // Show the modal
                modal.style.display = 'flex';            
            });
        }).catch(error => {
            alert(error.message);
        });


    }

    function handleLinkAndDescription(details, texts, lang, loadedTexts) {
        const element = document.getElementById(`link-${lang}`);
        const langText = loadedTexts && loadedTexts[lang] && loadedTexts[lang].text;
        if (langText) {
            const rawLink = details.descriptions && details.descriptions[`${lang}_link`];
            const link = normalizeLink(rawLink);
            if (link) {
                element.href = link;
                element.target = "_blank";
                element.style.pointerEvents = 'auto';
                element.style.cursor = 'pointer';
            } else {
                element.removeAttribute('href');
                element.style.pointerEvents = 'none';
                element.style.cursor = 'default';
            }
            element.style.display = '';
            element.innerText = langText;
            texts.push(details[`alt_${lang}`]);
            textLangs.push(lang);
        } else {
            element.style.display = 'none';
        }
    }

    function normalizeLink(rawLink) {
        if (!rawLink) return '';
        if (typeof rawLink === 'string' && rawLink.trim().startsWith('{')) {
            try {
                const parsed = JSON.parse(rawLink);
                if (parsed && parsed.url) return parsed.url;
            } catch (e) {
                console.warn('Failed to parse link json', rawLink);
                return '';
            }
        }
        return rawLink;
    }

    function loadEventTexts(details) {
        if (details.texts && Object.keys(details.texts).length) {
            return Promise.resolve(details.texts);
        }
        if (!details.descriptions) {
            return Promise.resolve({});
        }
        const languages = ["ru", "ua", "en"];
        const textPromises = languages.map(lang => {
            const textUrl = details.descriptions[lang];
            if (!textUrl) return null;
            const cacheKey = `${details.eventDate}-${lang}`;
            if (poemCache.has(cacheKey)) {
                return poemCache.get(cacheKey);
            }
            const fetchPromise = fetch(textUrl)
                .then(response => {
                    if (!response.ok) throw new Error(`Failed to load ${lang} text`);
                    return response.text();
                })
                .then(text => ({ lang, text, author: extractAuthor(text) }))
                .catch(error => {
                    console.error(`Error fetching the description for ${lang}:`, error);
                    return null; // Return null in case of error
                });
            poemCache.set(cacheKey, fetchPromise);
            return fetchPromise;
        }).filter(Boolean);

        return Promise.all(textPromises).then(texts => {
            const textMap = texts.reduce((acc, result) => {
                if (result) {
                    const { lang, text, author } = result;
                    acc[lang] = { text, author };
                }
                return acc;
            }, {});
            details.texts = textMap;
            return textMap;
        });
    }

    function extractAuthor(text) {
        const lines = text.split('\n').filter(line => line.trim() !== '');
        return lines[lines.length - 1] || '';
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
