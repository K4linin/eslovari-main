from django.core.management.base import BaseCommand
from django.db import transaction

from dictionary.models import Article, CardSet, Entry, Tag

TAGS = {
    "Программирование": "Код, функции, переменные и всё, что пишет разработчик",
    "Веб": "Фронтенд, бэкенд, HTTP и браузеры",
    "Базы данных": "Таблицы, запросы, индексы и транзакции",
    "DevOps": "Сборка, доставка и эксплуатация",
    "Git": "Контроль версий и командная работа с кодом",
    "Безопасность": "Защита данных, аккаунтов и серверов",
    "Командная работа": "Митинги, задачи, ревью и переписка",
}

# (слово, перевод, транскрипция, описание, пример, темы)
WORDS = [
    ("variable", "переменная", "[ˈveəriəbl]", "A named place in memory that stores a value.", "Store the user name in a variable.", ["Программирование"]),
    ("function", "функция", "[ˈfʌŋkʃn]", "A reusable block of code that performs a task.", "This function returns the total price.", ["Программирование"]),
    ("argument", "аргумент", "[ˈɑːɡjumənt]", "A value passed to a function when it is called.", "Pass the file path as an argument.", ["Программирование"]),
    ("loop", "цикл", "[luːp]", "Code that repeats while a condition is true.", "The loop runs ten times.", ["Программирование"]),
    ("condition", "условие", "[kənˈdɪʃn]", "An expression that is either true or false.", "Check the condition before saving.", ["Программирование"]),
    ("array", "массив", "[əˈreɪ]", "An ordered collection of elements.", "Sort the array by date.", ["Программирование"]),
    ("string", "строка", "[strɪŋ]", "A sequence of characters, like text.", "Convert the number to a string.", ["Программирование"]),
    ("integer", "целое число", "[ˈɪntɪdʒə]", "A whole number without a fractional part.", "The age must be an integer.", ["Программирование"]),
    ("exception", "исключение", "[ɪkˈsepʃn]", "An error event that interrupts the normal flow of a program.", "Catch the exception and log it.", ["Программирование"]),
    ("bug", "ошибка, баг", "[bʌɡ]", "A mistake in code that causes wrong behaviour.", "We found a bug in the login form.", ["Программирование", "Командная работа"]),
    ("debug", "отлаживать", "[ˌdiːˈbʌɡ]", "To find and fix errors in code.", "I spent an hour debugging this test.", ["Программирование"]),
    ("library", "библиотека", "[ˈlaɪbrəri]", "A collection of ready-made code you can reuse.", "We use a library to parse Excel files.", ["Программирование"]),
    ("framework", "фреймворк", "[ˈfreɪmwɜːk]", "A structure that defines how an application is built.", "Django is a Python web framework.", ["Программирование", "Веб"]),
    ("refactor", "рефакторить", "[riːˈfæktə]", "To improve code structure without changing behaviour.", "Let's refactor this module before adding features.", ["Программирование"]),
    ("deprecated", "устаревший", "[ˈdeprəkeɪtɪd]", "Still available but no longer recommended; will be removed.", "This method is deprecated since version 3.", ["Программирование"]),
    ("request", "запрос", "[rɪˈkwest]", "A message sent by a client to a server.", "The browser sends a GET request.", ["Веб"]),
    ("response", "ответ", "[rɪˈspɒns]", "A message the server sends back to the client.", "The response contains JSON data.", ["Веб"]),
    ("endpoint", "конечная точка (API)", "[ˈendpɔɪnt]", "A URL where an API can be accessed.", "Call the /users endpoint to get the list.", ["Веб"]),
    ("frontend", "фронтенд", "[ˈfrʌntend]", "The part of an application users see and interact with.", "She works on the frontend in React.", ["Веб"]),
    ("backend", "бэкенд", "[ˈbækend]", "The server side of an application: logic and data.", "The backend validates every request.", ["Веб"]),
    ("browser", "браузер", "[ˈbraʊzə]", "A program for viewing web pages.", "Clear the browser cache and reload.", ["Веб"]),
    ("cookie", "куки", "[ˈkʊki]", "A small piece of data the browser stores for a website.", "The session ID is stored in a cookie.", ["Веб", "Безопасность"]),
    ("layout", "макет, вёрстка", "[ˈleɪaʊt]", "The arrangement of elements on a page.", "The layout breaks on small screens.", ["Веб"]),
    ("responsive", "адаптивный", "[rɪˈspɒnsɪv]", "Adjusting to different screen sizes.", "Make the page responsive for phones.", ["Веб"]),
    ("query", "запрос (к БД)", "[ˈkwɪəri]", "A request for data from a database.", "This query is too slow.", ["Базы данных"]),
    ("table", "таблица", "[ˈteɪbl]", "A set of data organised in rows and columns.", "Add a new column to the users table.", ["Базы данных"]),
    ("index", "индекс", "[ˈɪndeks]", "A structure that speeds up searching in a database.", "Create an index on the email field.", ["Базы данных"]),
    ("primary key", "первичный ключ", "[ˈpraɪməri kiː]", "A column that uniquely identifies each row.", "The id is the primary key.", ["Базы данных"]),
    ("transaction", "транзакция", "[trænˈzækʃn]", "A group of operations that succeed or fail together.", "Wrap the transfer in a transaction.", ["Базы данных"]),
    ("migration", "миграция", "[maɪˈɡreɪʃn]", "A versioned change to the database schema.", "Run the migrations after deploying.", ["Базы данных", "DevOps"]),
    ("backup", "резервная копия", "[ˈbækʌp]", "A copy of data kept in case the original is lost.", "We make a backup every night.", ["Базы данных", "DevOps"]),
    ("deploy", "развёртывать, выкладывать", "[dɪˈplɔɪ]", "To release an application to a server so users can access it.", "We deploy to production on Fridays. Just kidding.", ["DevOps"]),
    ("server", "сервер", "[ˈsɜːvə]", "A computer that provides services to other computers.", "The server is down again.", ["DevOps", "Веб"]),
    ("container", "контейнер", "[kənˈteɪnə]", "An isolated package with an app and its dependencies.", "Run the app in a Docker container.", ["DevOps"]),
    ("pipeline", "конвейер (CI/CD)", "[ˈpaɪplaɪn]", "An automated sequence of build, test and deploy steps.", "The pipeline failed on the test stage.", ["DevOps"]),
    ("environment", "окружение", "[ɪnˈvaɪrənmənt]", "A setup where software runs: dev, staging, production.", "Check the variable in the staging environment.", ["DevOps"]),
    ("downtime", "простой", "[ˈdaʊntaɪm]", "A period when a service is unavailable.", "The update caused five minutes of downtime.", ["DevOps"]),
    ("rollback", "откат", "[ˈrəʊlbæk]", "Returning to a previous working version.", "Do a rollback if the release breaks.", ["DevOps", "Базы данных"]),
    ("log", "журнал, лог", "[lɒɡ]", "A record of events that happen in a system.", "Look at the logs to find the error.", ["DevOps"]),
    ("scalable", "масштабируемый", "[ˈskeɪləbl]", "Able to handle growth in users or data.", "The architecture must be scalable.", ["DevOps"]),
    ("repository", "репозиторий", "[rɪˈpɒzətri]", "A storage for code and its change history.", "Clone the repository to your laptop.", ["Git"]),
    ("commit", "коммит, фиксировать", "[kəˈmɪt]", "A saved snapshot of changes in Git.", "Write a clear commit message.", ["Git"]),
    ("branch", "ветка", "[brɑːntʃ]", "An independent line of development.", "Create a new branch for this feature.", ["Git"]),
    ("merge", "слияние, сливать", "[mɜːdʒ]", "To combine changes from different branches.", "Merge the branch after the review.", ["Git"]),
    ("pull request", "пулл-реквест", "[pʊl rɪˈkwest]", "A proposal to merge changes, open for review.", "I opened a pull request for the fix.", ["Git", "Командная работа"]),
    ("conflict", "конфликт", "[ˈkɒnflɪkt]", "When two changes touch the same lines and Git can't merge them.", "Resolve the merge conflict manually.", ["Git"]),
    ("clone", "клонировать", "[kləʊn]", "To make a local copy of a remote repository.", "Clone the project and install dependencies.", ["Git"]),
    ("password", "пароль", "[ˈpɑːswɜːd]", "A secret word used to prove identity.", "Never reuse the same password.", ["Безопасность"]),
    ("encryption", "шифрование", "[ɪnˈkrɪpʃn]", "Converting data into a code to prevent unauthorised access.", "All traffic is protected with encryption.", ["Безопасность"]),
    ("vulnerability", "уязвимость", "[ˌvʌlnərəˈbɪləti]", "A weakness that can be exploited by an attacker.", "The scanner found a critical vulnerability.", ["Безопасность"]),
    ("authentication", "аутентификация", "[ɔːˌθentɪˈkeɪʃn]", "Checking who a user is.", "Two-factor authentication adds a second step.", ["Безопасность"]),
    ("authorization", "авторизация", "[ˌɔːθəraɪˈzeɪʃn]", "Checking what a user is allowed to do.", "Authorization failed: access denied.", ["Безопасность"]),
    ("firewall", "межсетевой экран", "[ˈfaɪəwɔːl]", "A system that filters network traffic.", "Open port 443 in the firewall.", ["Безопасность", "DevOps"]),
    ("brute force", "перебор (атака)", "[bruːt fɔːs]", "An attack that tries many passwords until one works.", "The login form is protected from brute force.", ["Безопасность"]),
    ("hash", "хэш", "[hæʃ]", "A fixed-length fingerprint of data that can't be reversed.", "Passwords are stored as hashes.", ["Безопасность"]),
    ("token", "токен", "[ˈtəʊkən]", "A piece of data that proves identity or permission.", "The API token expires in one hour.", ["Безопасность", "Веб"]),
    ("deadline", "крайний срок", "[ˈdedlaɪn]", "The time by which work must be done.", "The deadline is next Monday.", ["Командная работа"]),
    ("estimate", "оценка, оценивать", "[ˈestɪmət]", "An approximate calculation of time or effort.", "Can you estimate this task?", ["Командная работа"]),
    ("requirement", "требование", "[rɪˈkwaɪəmənt]", "Something a product must do or have.", "The requirements changed again.", ["Командная работа"]),
    ("feedback", "обратная связь", "[ˈfiːdbæk]", "Comments about how well something works.", "Thanks for the feedback on my code.", ["Командная работа"]),
    ("stand-up", "стендап, планёрка", "[ˈstænd ʌp]", "A short daily team meeting.", "Let's discuss it after the stand-up.", ["Командная работа"]),
    ("code review", "ревью кода", "[kəʊd rɪˈvjuː]", "Checking a colleague's code before merging.", "The code review took two days.", ["Командная работа", "Git"]),
    ("release", "релиз, выпуск", "[rɪˈliːs]", "A version of software made available to users.", "The release is planned for June.", ["Командная работа", "DevOps"]),
    ("workaround", "обходной путь", "[ˈwɜːkəraʊnd]", "A temporary way to avoid a problem.", "There is a workaround until we fix it.", ["Командная работа", "Программирование"]),
    ("blocker", "блокер", "[ˈblɒkə]", "An issue that stops work from moving forward.", "Do you have any blockers?", ["Командная работа"]),
]

SETS = [
    ("Первые 20 слов разработчика", "Самые частые термины из кода и документации — начните с них.",
     ["variable", "function", "argument", "loop", "condition", "array", "string", "integer", "exception", "bug",
      "debug", "library", "framework", "request", "response", "server", "commit", "branch", "deploy", "log"]),
    ("Git без паники", "Ветки, коммиты, слияния и конфликты.",
     ["repository", "commit", "branch", "merge", "pull request", "conflict", "clone", "code review", "rollback"]),
    ("Безопасность для всех", "Слова, которые встретятся в любой статье о защите данных.",
     ["password", "encryption", "vulnerability", "authentication", "authorization", "firewall", "brute force", "hash", "token", "cookie"]),
    ("Английский для созвонов", "Чтобы уверенно говорить на стендапе и ревью.",
     ["deadline", "estimate", "requirement", "feedback", "stand-up", "code review", "release", "workaround", "blocker", "bug"]),
]

ARTICLES = [
    ("My first day as a junior developer", "A1",
     "Простой рассказ о первом рабочем дне: знакомимся с базовой лексикой.",
     ["Командная работа", "Программирование"],
     """Hello! My name is Anna. I am a junior developer. Today is my first day at work.

In the morning I meet my team. We have a short stand-up. Every person says what they did yesterday and what they will do today.

My mentor gives me a laptop. I clone the repository and run the project. It works! Then I find a small bug in the login page. I fix it and make my first commit.

In the evening I open a pull request. My mentor writes some feedback. I am tired, but I am happy."""),
    ("What happens when you open a website?", "A2",
     "Что происходит между вводом адреса и появлением страницы: запрос, сервер, ответ.",
     ["Веб"],
     """You type an address in your browser and press Enter. What happens next?

First, the browser finds the server. It asks a special system called DNS: "Where is this website?" DNS answers with an IP address.

Then the browser sends a request to the server. The request says: "Please give me this page." The server reads the request, gets data from a database and builds a response.

The response comes back to the browser. It contains HTML, CSS and JavaScript. The browser draws the layout, loads images and runs scripts. Now you can see the page!

All of this usually takes less than one second."""),
    ("Why we use Git branches", "B1",
     "Зачем команды работают в ветках и как устроен путь изменения от коммита до релиза.",
     ["Git", "Командная работа"],
     """Imagine five developers editing the same files at the same time. Without a plan, they would constantly overwrite each other's work. This is why teams use branches.

A branch is an independent line of development. When you start a new feature, you create a branch from the main one. You can commit as often as you want, experiment and even break things — the main branch stays safe.

When the feature is ready, you open a pull request. Your colleagues review the code, leave comments and suggest improvements. After the review, the branch is merged.

Sometimes Git can't merge changes automatically because two people edited the same lines. This is called a conflict. Don't panic: open the file, decide which version is correct, and commit the result.

Good branch names and clear commit messages make the history easy to read. Your future self will thank you."""),
    ("Passwords are not enough", "B2",
     "Почему одного пароля мало и как работает двухфакторная аутентификация.",
     ["Безопасность"],
     """Every year, billions of passwords leak from hacked websites. Attackers collect these lists and try them on other services — a technique known as credential stuffing. If you reuse the same password everywhere, one breach can open all your accounts.

Well-designed systems never store passwords in plain text. Instead, they store a hash — a one-way fingerprint produced by an algorithm such as Argon2. Even if the database is stolen, recovering the original passwords is extremely expensive.

Login forms should also resist brute force attacks. A common approach is to lock an account for a while after several failed attempts from the same address.

But the strongest protection is two-factor authentication. After entering the password, you type a short code generated by an app on your phone. The code changes every 30 seconds, so a stolen password alone is useless.

Turn on two-factor authentication wherever you can. It takes one minute and saves a lot of trouble."""),
    ("The hidden cost of downtime", "C1",
     "Как простой сервиса бьёт по бизнесу и какие практики DevOps помогают его избежать.",
     ["DevOps"],
     """When a service goes down, the immediate cost is obvious: users can't log in, orders aren't placed and support channels overflow. Yet the long-term consequences are often more significant — eroded trust, churn and engineers pulled away from planned work to fight fires.

Mature teams treat reliability as a feature rather than an afterthought. Deployments are automated through a pipeline that builds, tests and ships every change in the same reproducible way. Containers ensure that the environment in production mirrors the one developers use locally, eliminating an entire category of "it works on my machine" incidents.

Equally important is the ability to recover quickly. A well-rehearsed rollback procedure turns a potential outage into a minor blip. Regular, verified backups — not merely scheduled ones — guarantee that data can be restored when everything else fails.

Finally, observability closes the loop. Structured logs, metrics and alerts let engineers notice degradation before customers do. Downtime may never be eliminated entirely, but its impact can be made remarkably small."""),
]


class Command(BaseCommand):
    help = "Загружает демо-слова, темы, наборы карточек и статьи (повторный запуск безопасен)."

    @transaction.atomic
    def handle(self, *args, **options):
        tags = {}
        for name, description in TAGS.items():
            tags[name], _ = Tag.objects.get_or_create(name=name, defaults={"description": description})

        created = 0
        entries = {}
        for word, translation, transcription, description, example, tag_names in WORDS:
            entry = Entry.objects.filter(word__iexact=word).first()
            if entry is None:
                entry = Entry.objects.create(
                    word=word, translation=translation, transcription=transcription,
                    description=description, example=example,
                )
                created += 1
            entry.tags.add(*(tags[n] for n in tag_names))
            entries[word] = entry

        for title, description, words in SETS:
            card_set, _ = CardSet.objects.get_or_create(title=title, defaults={"description": description})
            card_set.entries.add(*(entries[w] for w in words))

        for title, level, summary, tag_names, body in ARTICLES:
            article, _ = Article.objects.get_or_create(
                title=title, defaults={"level": level, "summary": summary, "body": body}
            )
            article.tags.add(*(tags[n] for n in tag_names))

        self.stdout.write(self.style.SUCCESS(
            f"Готово: слов добавлено {created} (всего {Entry.objects.count()}), "
            f"тем {Tag.objects.count()}, наборов {CardSet.objects.count()}, статей {Article.objects.count()}."
        ))
