# 统一 benchmark 样例集

- 生成时间：2026-10-31T04:05:54
- 抽样：每个来源 40 条，seed=42
- 总计：320 条

## 来源

| 来源 | 可用 | 版本 | 原始条数 | 抽样 | 许可 |
|:---|:---:|:---|:---:|:---:|:---|
| tau2-bench | ✅ | cc1df47 | 114 | 40 | MIT |
| bfcl-v4 | ✅ | 6ea5797 | 640 | 40 | Apache-2.0 |
| rgb | ✅ | 65ec39e | 300 | 40 | CC BY-NC-SA 4.0 |
| multihop-rag | ✅ | c1c1287 | 2556 | 40 | ODC-BY 1.0 |
| gaia | ✅ | unknown | 165 | 40 | see HuggingFace dataset card |
| swe-bench | ✅ | unknown | 500 | 40 | MIT (see repo) |
| webarena | ✅ | unknown | 812 | 40 | Apache-2.0 |
| osworld | ✅ | unknown | 418 | 40 | Apache-2.0 |

## 分类

- coding: 40
- customer_service: 40
- general_assistant: 40
- os_chrome: 3
- os_excel: 3
- os_gimp: 3
- os_libreoffice_calc: 3
- os_libreoffice_impress: 3
- os_libreoffice_writer: 3
- os_multi_app: 3
- os_multi_apps: 3
- os_os: 3
- os_ppt: 3
- os_thunderbird: 3
- os_vlc: 3
- os_vs_code: 2
- os_word: 2
- rag_multihop_comparison_query: 10
- rag_multihop_inference_query: 10
- rag_multihop_null_query: 10
- rag_multihop_temporal_query: 10
- rag_rgb: 40
- tool_calling_irrelevance: 20
- tool_calling_simple: 20
- web: 40

## AgentGuide Bucket

- adversarial: 30
- capability: 250
- multi_turn: 40

## 样例

| ID | 来源 | Bucket | 类别 | 任务 | 评分 |
|:---|:---|:---|:---|:---|:---|
| bfcl-irrelevance_45 | bfcl-v4 | adversarial | tool_calling_irrelevance | Calculate the sine of 45 degree. | code |
| bfcl-irrelevance_113 | bfcl-v4 | adversarial | tool_calling_irrelevance | Find me restaurants in London | code |
| bfcl-irrelevance_9 | bfcl-v4 | adversarial | tool_calling_irrelevance | Find the definite integral of f(x)=x^2 from x=1 to x=3. | code |
| bfcl-irrelevance_85 | bfcl-v4 | adversarial | tool_calling_irrelevance | Who won the presidential election in 2020? | code |
| bfcl-irrelevance_105 | bfcl-v4 | adversarial | tool_calling_irrelevance | What are the top five flower species for pollination in Sout | code |
| bfcl-irrelevance_197 | bfcl-v4 | adversarial | tool_calling_irrelevance | Who won the game of Monopoly last night? | code |
| bfcl-irrelevance_209 | bfcl-v4 | adversarial | tool_calling_irrelevance | How to build a new PC? | code |
| bfcl-irrelevance_132 | bfcl-v4 | adversarial | tool_calling_irrelevance | What was the casualty number of the Battle of Waterloo? | code |
| bfcl-irrelevance_231 | bfcl-v4 | adversarial | tool_calling_irrelevance | Find a Thai restaurant in Chicago with vegetarian options. | code |
| bfcl-irrelevance_44 | bfcl-v4 | adversarial | tool_calling_irrelevance | What is the gene sequence for evolutionary changes in whales | code |
| bfcl-irrelevance_126 | bfcl-v4 | adversarial | tool_calling_irrelevance | What is the effect of economic status on happiness levels? | code |
| bfcl-irrelevance_193 | bfcl-v4 | adversarial | tool_calling_irrelevance | Who is the top scorer for Los Angeles Lakers? | code |
| bfcl-irrelevance_29 | bfcl-v4 | adversarial | tool_calling_irrelevance | Identify the number of the mitochondria in a cell. | code |
| bfcl-irrelevance_78 | bfcl-v4 | adversarial | tool_calling_irrelevance | What is the gold price today in USA? | code |
| bfcl-irrelevance_115 | bfcl-v4 | adversarial | tool_calling_irrelevance | How long would it take to travel from Boston to New York by  | code |
| bfcl-irrelevance_140 | bfcl-v4 | adversarial | tool_calling_irrelevance | Who discovered electricity? | code |
| bfcl-irrelevance_21 | bfcl-v4 | adversarial | tool_calling_irrelevance | What's the magnetic field at a point 4m away from a wire car | code |
| bfcl-irrelevance_123 | bfcl-v4 | adversarial | tool_calling_irrelevance | What are the calories of a Big Mac? | code |
| bfcl-irrelevance_190 | bfcl-v4 | adversarial | tool_calling_irrelevance | Who is currently the top ranked tennis player? | code |
| bfcl-irrelevance_206 | bfcl-v4 | adversarial | tool_calling_irrelevance | Find the best character to use against a dragon in DragonSla | code |
| bfcl-simple_python_221 | bfcl-v4 | capability | tool_calling_simple | What will be the population growth in London over the next f | code |
| bfcl-simple_python_182 | bfcl-v4 | capability | tool_calling_simple | Retrieve all the lawsuit details for case number XYZ123. | code |
| bfcl-simple_python_112 | bfcl-v4 | capability | tool_calling_simple | Calculate the probability of drawing a king from a deck of c | code |
| bfcl-simple_python_157 | bfcl-v4 | capability | tool_calling_simple | Find out if an individual John Doe with a birthday 01-01-198 | code |
| bfcl-simple_python_99 | bfcl-v4 | capability | tool_calling_simple | Plot a sine wave from 0 to 2 pi with a frequency of 5 Hz. | code |
| bfcl-simple_python_12 | bfcl-v4 | capability | tool_calling_simple | Calculate the circumference of a circle with radius 3 | code |
| bfcl-simple_python_114 | bfcl-v4 | capability | tool_calling_simple | Find the probability of getting exactly 5 heads in 10 fair c | code |
| bfcl-simple_python_353 | bfcl-v4 | capability | tool_calling_simple | What are some gluten-free recipes for dinner? | code |
| bfcl-simple_python_335 | bfcl-v4 | capability | tool_calling_simple | Find a Card of rank 'Queen' and suit 'Hearts' in the deck. | code |
| bfcl-simple_python_134 | bfcl-v4 | capability | tool_calling_simple | Predict the total expected profit of stocks XYZ in 5 years g | code |
| bfcl-simple_python_342 | bfcl-v4 | capability | tool_calling_simple | Find all multi-player games released in 2019 with an ESRB ra | code |
| bfcl-simple_python_228 | bfcl-v4 | capability | tool_calling_simple | Find three personality traits of people who like jogging. | code |
| bfcl-simple_python_255 | bfcl-v4 | capability | tool_calling_simple | Get the biography and main contributions of Pope Innocent II | code |
| bfcl-simple_python_101 | bfcl-v4 | capability | tool_calling_simple | Calculate the speed of an object in km/h if it traveled 450  | code |
| bfcl-simple_python_269 | bfcl-v4 | capability | tool_calling_simple | Calculate the compound interest of an investment of $10,000  | code |
| bfcl-simple_python_204 | bfcl-v4 | capability | tool_calling_simple | Find restaurants near me within 10 miles that offer Chinese  | code |
| bfcl-simple_python_165 | bfcl-v4 | capability | tool_calling_simple | Retrieve cases from 2020 about theft crimes in Los Angeles,  | code |
| bfcl-simple_python_230 | bfcl-v4 | capability | tool_calling_simple | Who was the King of France in 1510? | code |
| bfcl-simple_python_254 | bfcl-v4 | capability | tool_calling_simple | Retrieve the historic dates and facts related to Christianit | code |
| bfcl-simple_python_185 | bfcl-v4 | capability | tool_calling_simple | What will be the weather in New York in the next 72 hours in | code |
| gaia-a0068077-79f4-461a-adfe-75c1a4148545 | gaia | capability | general_assistant | What was the actual enrollment count of the clinical trial o | mixed |
| gaia-df6561b2-7ee5-4540-baab-5095f742716a | gaia | capability | general_assistant | When you take the average of the standard population deviati | mixed |
| gaia-73c1b9fe-ee1d-4cf4-96ca-35c08f97b054 | gaia | capability | general_assistant | According to the USGS, in what year was the American Alligat | mixed |
| gaia-08c0b6e9-1b43-4c2e-ae55-4e3fce2c2715 | gaia | capability | general_assistant | In the film Goldfinger, what color was the object that James | mixed |
| gaia-db4fd70a-2d37-40ea-873f-9433dc5e301f | gaia | capability | general_assistant | As of May 2023, how many stops are between South Station and | mixed |
| gaia-c526d8d6-5987-4da9-b24c-83466fa172f3 | gaia | capability | general_assistant | In the NIH translation of the original 1913 Michaelis-Menten | mixed |
| gaia-d1af70ea-a9a4-421a-b9cc-94b5e02f1788 | gaia | capability | general_assistant | As of the 2020 census, what was the population difference be | mixed |
| gaia-20194330-9976-4043-8632-f8485c6c71b2 | gaia | capability | general_assistant | The YouTube channel Game Grumps began a Let’s Play of the ga | mixed |
| gaia-7bd855d8-463d-4ed5-93ca-5fe35145f733 | gaia | capability | general_assistant | The attached Excel file contains the sales of menu items for | mixed |
| gaia-a7feb290-76bb-4cb7-8800-7edaf7954f2f | gaia | capability | general_assistant | How many High Energy Physics - Lattice articles listed in Ja | mixed |
| gaia-71345b0a-9c7d-4b50-b2bf-937ec5879845 | gaia | capability | general_assistant | On a leap day before the year 2008, a joke was removed from  | mixed |
| gaia-56db2318-640f-477a-a82f-bc93ad13e882 | gaia | capability | general_assistant | The following numbers function similarly to ISBN 13 numbers, | mixed |
| gaia-da52d699-e8d2-4dc5-9191-a2199e0b6a9b | gaia | capability | general_assistant | The attached spreadsheet contains a list of books I read in  | mixed |
| gaia-6359a0b1-8f7b-499b-9336-840f9ab90688 | gaia | capability | general_assistant | What is the area of the green polygon in the attached file?  | mixed |
| gaia-a3fbeb63-0e8c-4a11-bff6-0e3b484c3e9c | gaia | capability | general_assistant | How many slides in this PowerPoint presentation mention crus | mixed |
| gaia-366e2f2b-8632-4ef2-81eb-bc3877489217 | gaia | capability | general_assistant | The attached file lists accommodations in the resort town of | mixed |
| gaia-2dfc4c37-fec1-4518-84a7-10095d30ad75 | gaia | capability | general_assistant | According to Box Office Mojo's 2020 Worldwide Box Office lis | mixed |
| gaia-624cbf11-6a41-4692-af9c-36b3e5ca3130 | gaia | capability | general_assistant | What's the last line of the rhyme under the flavor name on t | mixed |
| gaia-cf106601-ab4f-4af9-b045-5295fe67b37d | gaia | capability | general_assistant | What country had the least number of athletes at the 1928 Su | mixed |
| gaia-0a3cd321-3e76-4622-911b-0fda2e5d6b1a | gaia | capability | general_assistant | According to the World Bank, which countries had gross savin | mixed |
| gaia-b816bfce-3d80-4913-a07d-69b752ce6377 | gaia | capability | general_assistant | In Emily Midkiff's June 2014 article in a journal named for  | mixed |
| gaia-e9a2c537-8232-4c3f-85b0-b52de6bcba99 | gaia | capability | general_assistant | The attached file shows a list of books in the collection of | mixed |
| gaia-4fc2f1ae-8625-45b5-ab34-ad4433bc21f8 | gaia | capability | general_assistant | Who nominated the only Featured Article on English Wikipedia | mixed |
| gaia-56137764-b4e0-45b8-9c52-1866420c3df5 | gaia | capability | general_assistant | Which contributor to the version of OpenCV where support was | mixed |
| gaia-2a649bb1-795f-4a01-b3be-9a01868dae73 | gaia | capability | general_assistant | What are the EC numbers of the two most commonly used chemic | mixed |
| gaia-72c06643-a2fa-4186-aa5c-9ec33ae9b445 | gaia | capability | general_assistant | What is the volume in milliliters of a system comprised of 0 | mixed |
| gaia-cca70ce6-1952-45d2-acd4-80c903b0bc49 | gaia | capability | general_assistant | Look at the attached image. The quiz is scored as follows:   | mixed |
| gaia-544b7f0c-173a-4377-8d56-57b36eb26ddf | gaia | capability | general_assistant | In Valentina Re’s contribution to the 2017 book “World Build | mixed |
| gaia-0ff53813-3367-4f43-bcbd-3fd725c1bf4b | gaia | capability | general_assistant | What two-word type of model did Manash Pratim Kashyap's and  | mixed |
| gaia-9b54f9d9-35ee-4a14-b62f-d130ea00317f | gaia | capability | general_assistant | Which of the text elements under CATEGORIES in the XML would | mixed |
| gaia-dd3c7503-f62a-4bd0-9f67-1b63b94194cc | gaia | capability | general_assistant | Use density measures from the chemistry materials licensed b | mixed |
| gaia-f46b4380-207e-4434-820b-f32ce04ae2a4 | gaia | capability | general_assistant | It is 1999. Before you party like it is 1999, please assist  | mixed |
| gaia-50ad0280-0819-4bd9-b275-5de32d3b5bcb | gaia | capability | general_assistant | Pull out the sentence in the following 5x7 block of text. Re | mixed |
| gaia-023e9d44-96ae-4eed-b912-244ee8c3b994 | gaia | capability | general_assistant | It's May 2023, and I'm about to drive across the U.S. from C | mixed |
| gaia-04a04a9b-226c-43fd-b319-d5e89743676f | gaia | capability | general_assistant | If we assume all articles published by Nature in 2020 (artic | mixed |
| gaia-ecbc4f94-95a3-4cc7-b255-6741a458a625 | gaia | capability | general_assistant | How many images are there in the latest 2022 Lego english wi | mixed |
| gaia-32102e3e-d12a-4209-9163-7b3a104efe5d | gaia | capability | general_assistant | The attached spreadsheet shows the inventory for a movie and | mixed |
| gaia-5f982798-16b9-4051-ab57-cfc7ebdb2a91 | gaia | capability | general_assistant | I read a paper about multiwavelength observations of fast ra | mixed |
| gaia-b2c257e0-3ad7-4f05-b8e3-d9da973be36e | gaia | capability | general_assistant | If this whole pint is made up of ice cream, how many percent | mixed |
| gaia-dc28cf18-6431-458b-83ef-64b3ce566c10 | gaia | capability | general_assistant | My family reunion is this week, and I was assigned the mashe | mixed |
| multihop-599 | multihop-rag | capability | rag_multihop_comparison_query | Does the Sporting News article suggest that Dylan Cease, Cor | mixed |
| multihop-1387 | multihop-rag | capability | rag_multihop_comparison_query | Does the Engadget article claim that ChatGPT has reached its | mixed |
| multihop-35 | multihop-rag | capability | rag_multihop_comparison_query | Does the TechCrunch article on GPT-4 suggest a greater ease  | mixed |
| multihop-338 | multihop-rag | capability | rag_multihop_comparison_query | Does the Yahoo News article praise the Biden administration' | mixed |
| multihop-2466 | multihop-rag | capability | rag_multihop_comparison_query | Does the Polygon article suggest that "Video games in 2023"  | mixed |
| multihop-933 | multihop-rag | capability | rag_multihop_comparison_query | Does the CBSSports.com article claim that Caesars Sportsbook | mixed |
| multihop-90 | multihop-rag | capability | rag_multihop_comparison_query | Does 'The Verge' claim that Google has the ability to resolv | mixed |
| multihop-561 | multihop-rag | capability | rag_multihop_comparison_query | Did the 'Sporting News' article mention Kevin Behrens, Chris | mixed |
| multihop-1075 | multihop-rag | capability | rag_multihop_comparison_query | Does the article from The Verge suggest that Sam Bankman-Fri | mixed |
| multihop-940 | multihop-rag | capability | rag_multihop_comparison_query | Does the TechCrunch article suggest that Sam Bankman-Fried's | mixed |
| multihop-341 | multihop-rag | capability | rag_multihop_inference_query | Which company, reported by both TechCrunch and The Verge, ha | mixed |
| multihop-669 | multihop-rag | capability | rag_multihop_inference_query | Which company is at the center of antitrust legal challenges | mixed |
| multihop-1599 | multihop-rag | capability | rag_multihop_inference_query | Who is the individual under 30, previously reported by a wor | mixed |
| multihop-1121 | multihop-rag | capability | rag_multihop_inference_query | Which company is at the center of allegations involving mani | mixed |
| multihop-873 | multihop-rag | capability | rag_multihop_inference_query | Who is the individual whose trial involved allegations of fr | mixed |
| multihop-0 | multihop-rag | capability | rag_multihop_inference_query | Who is the individual associated with the cryptocurrency ind | mixed |
| multihop-1892 | multihop-rag | capability | rag_multihop_inference_query | Which pop star, who became a public figure unable to avoid a | mixed |
| multihop-2249 | multihop-rag | capability | rag_multihop_inference_query | What is the name of the organization, founded in late 2015,  | mixed |
| multihop-990 | multihop-rag | capability | rag_multihop_inference_query | Which institution, recently covered by both 'The Sydney Morn | mixed |
| multihop-1956 | multihop-rag | capability | rag_multihop_inference_query | Who is the individual under 30, previously associated with J | mixed |
| multihop-2516 | multihop-rag | adversarial | rag_multihop_null_query | Considering the information from a Reuters article on the la | mixed |
| multihop-732 | multihop-rag | adversarial | rag_multihop_null_query | Based on a Bloomberg article discussing Apple's future produ | mixed |
| multihop-311 | multihop-rag | adversarial | rag_multihop_null_query | Considering the information from an ESPN article detailing t | mixed |
| multihop-545 | multihop-rag | adversarial | rag_multihop_null_query | Considering the information from a New York Times article di | mixed |
| multihop-2256 | multihop-rag | adversarial | rag_multihop_null_query | Considering an article from The New York Times detailing Pat | mixed |
| multihop-1506 | multihop-rag | adversarial | rag_multihop_null_query | Considering the information from an article in The Economic  | mixed |
| multihop-357 | multihop-rag | adversarial | rag_multihop_null_query | Considering the information from a Washington Post article d | mixed |
| multihop-1976 | multihop-rag | adversarial | rag_multihop_null_query | Considering the information from a BBC article detailing Dem | mixed |
| multihop-955 | multihop-rag | adversarial | rag_multihop_null_query | Considering the information from an article by The Verge on  | mixed |
| multihop-1438 | multihop-rag | adversarial | rag_multihop_null_query | Considering the economic strategies discussed in a Bloomberg | mixed |
| multihop-1391 | multihop-rag | capability | rag_multihop_temporal_query | After the report by Business Today | Latest Stock Market And | mixed |
| multihop-850 | multihop-rag | capability | rag_multihop_temporal_query | Between the report from The Verge on Apple's defense of its  | mixed |
| multihop-43 | multihop-rag | capability | rag_multihop_temporal_query | Did the 'Fortune' report on Donald Trump's real estate valua | mixed |
| multihop-1072 | multihop-rag | capability | rag_multihop_temporal_query | Between the TechCrunch report on Epic Games' antitrust battl | mixed |
| multihop-1159 | multihop-rag | capability | rag_multihop_temporal_query | Between the 'Fortune' report on Donald Trump's real estate v | mixed |
| multihop-633 | multihop-rag | capability | rag_multihop_temporal_query | Did the Music Business Worldwide report on November 21, 2023 | mixed |
| multihop-2244 | multihop-rag | capability | rag_multihop_temporal_query | Has the focus of Taylor Swift coverage by 'The Independent - | mixed |
| multihop-839 | multihop-rag | capability | rag_multihop_temporal_query | Was there no change in the focus of reporting on Uber from s | mixed |
| multihop-1764 | multihop-rag | capability | rag_multihop_temporal_query | Between the TechCrunch report on Sam Altman's involvement wi | mixed |
| multihop-1073 | multihop-rag | capability | rag_multihop_temporal_query | Has the description of ChatGPT's capabilities by TechCrunch  | mixed |
| osworld-121ba48f-9e17-48ce-9bc6-a4fb17a7ebba | osworld | capability | os_chrome | Find Dota 2 game and add all DLC to cart. | code |
| osworld-f0b971a1-6831-4b9b-a50e-22a6e47f45ba | osworld | capability | os_chrome | Please help me find the score record for the Super Bowl of t | code |
| osworld-44ee5668-ecd5-4366-a6ce-c1c9b8d4e938 | osworld | capability | os_chrome | I am looking for an website address I accessed a month ago,  | code |
| osworld-3aaa4e37-dc91-482e-99af-132a612d40f3 | osworld | capability | os_excel | Could you help me to export the current sheet to a csv file? | code |
| osworld-eb03d19a-b88d-4de4-8a64-ca0ac66f426b | osworld | capability | os_excel | Transpose the table and paste it starting from B8. | code |
| osworld-ecb0df7a-4e8d-4a03-b162-053391d3afaf | osworld | capability | os_excel | Enable each cell in the column"Pass/Fail/Held" is a drop dow | code |
| osworld-e19bd559-633b-4b02-940f-d946248f088e | osworld | capability | os_gimp | Could you tone down the brightness of my photo at desktop? | code |
| osworld-734d6579-c07d-47a8-9ae2-13339795476b | osworld | capability | os_gimp | Could you fill the background layer with green color, leavin | code |
| osworld-7b7617bd-57cc-468e-9c91-40c4ec2bcb3d | osworld | capability | os_gimp | Set the minimum number of undo steps to 100. | code |
| osworld-4f07fbe9-70de-4927-a4d5-bb28bc12c52c | osworld | capability | os_libreoffice_calc | Here I want to use the numerical value from a cell in the te | code |
| osworld-abed40dc-063f-4598-8ba5-9fe749c0615d | osworld | capability | os_libreoffice_calc | Check the names in column "Names with duplicates" and put th | code |
| osworld-7efeb4b1-3d19-4762-b163-63328d66303b | osworld | capability | os_libreoffice_calc | Fill the Sequence Numbers as "No. #" in the "Seq No." column | code |
| osworld-0f84bef9-9790-432e-92b7-eece357603fb | osworld | capability | os_libreoffice_impress | On it Whenever I launch a LibreOffice Impress, it uses both  | code |
| osworld-af2d657a-e6b3-4c6a-9f67-9e3ed015974c | osworld | capability | os_libreoffice_impress | In the first slide, insert the title "Happy Family" and make | code |
| osworld-8979838c-54a5-4454-a2b8-3d135a1a5c8f | osworld | capability | os_libreoffice_impress | Give the slide a purple background color. Add the title to n | code |
| osworld-6ada715d-3aae-4a32-a6a7-429b2e43fb93 | osworld | capability | os_libreoffice_writer | Copy the screenshot 1.png from the desktop to where my curso | code |
| osworld-e528b65e-1107-4b8c-8988-490e4fece599 | osworld | capability | os_libreoffice_writer | Please help me make the first letter of each word to upperca | code |
| osworld-72b810ef-4156-4d09-8f08-a0cf57e7cefe | osworld | capability | os_libreoffice_writer | I am peer-reviewing my friend's course outline. I think the  | code |
| osworld-f918266a-b3e0-4914-865d-4faa564f1aef | osworld | capability | os_multi_app | Please complete the code and retrieve the output from the Py | code |
| osworld-09a37c51-e625-49f4-a514-20a773797a8a | osworld | capability | os_multi_app | I've received a request from my friend who asked for assista | code |
| osworld-c867c42d-a52d-4a24-8ae3-f75d256b5618 | osworld | capability | os_multi_app | Please assist me in exporting my contacts of Personal Addres | code |
| osworld-2373b66a-092d-44cb-bfd7-82e86e7a3b4d | osworld | capability | os_multi_apps | Monitor Ubuntu system resource usage using the sar command f | code |
| osworld-2c1ebcd7-9c6d-4c9a-afad-900e381ecd5e | osworld | capability | os_multi_apps | Could you please review the 'case study.docx' file located i | code |
| osworld-869de13e-bef9-4b91-ba51-f6708c40b096 | osworld | capability | os_multi_apps | Can you organize my desktop by identifying academic papers,  | code |
| osworld-5ced85fc-fa1a-4217-95fd-0fb530545ce2 | osworld | capability | os_os | Append "<br/>" to the end of each line in "1\n2\n3" and save | code |
| osworld-b6781586-6346-41cd-935a-a6b1487918fc | osworld | capability | os_os | I want to set my current time zone to UTC+0. Can you help me | code |
| osworld-37887e8c-da15-4192-923c-08fa390a176d | osworld | capability | os_os | Compress all files under "/tmp/test_files" that were last mo | code |
| osworld-a097acff-6266-4291-9fbd-137af7ecd439 | osworld | capability | os_ppt | Could you help me save my slides as pre.pptx on the Desktop? | code |
| osworld-455d3c66-7dc6-4537-a39a-36d3e9119df7 | osworld | capability | os_ppt | Could you help me export the PowerPoint file to a .png image | code |
| osworld-3b27600c-3668-4abd-8f84-7bcdebbccbdb | osworld | capability | os_ppt | Please make the background blue on all my slides. I was stuc | code |
| osworld-7b1e1ff9-bb85-49be-b01d-d6424be18cd0 | osworld | capability | os_thunderbird | Could you help me open up the profile management tabpage in  | code |
| osworld-a1af9f1c-50d5-4bc3-a51e-4d9b425ff638 | osworld | capability | os_thunderbird | Due to certain security considerations and the nature of my  | code |
| osworld-3f28fe4f-5d9d-4994-a456-efd78cfae1a3 | osworld | capability | os_thunderbird | Set up a plain text signature for my email account in Thunde | code |
| osworld-a5bbbcd5-b398-4c91-83d4-55e1e31bbb81 | osworld | capability | os_vlc | Enable VLC Minimal Interface in window mode so the bottom pl | code |
| osworld-7882ed6e-bece-4bf0-bada-c32dc1ddae72 | osworld | capability | os_vlc | Play the latest season of 'Stranger Things' purchased from t | code |
| osworld-d06f0d4d-2cd5-4ede-8de9-598629438c6e | osworld | capability | os_vlc | Can you change the color of the volume slider to black-ish c | code |
| osworld-971cbb5b-3cbf-4ff7-9e24-b5c84fcebfa6 | osworld | capability | os_vs_code | Please help me change the settings of VS Code so that every  | code |
| osworld-7aeae0e2-70ee-4705-821d-1bba5d5b2ddd | osworld | capability | os_vs_code | Please help me visualize all numpy arrays in current python  | code |
| osworld-b21acd93-60fd-4127-8a43-2f5178f4a830 | osworld | capability | os_word | I have been practicing professional writing lately. Now I am | code |
| osworld-ecc2413d-8a48-416e-a3a2-d30106ca36cb | osworld | capability | os_word | Hey, can you throw in a blank page right after this one? | code |
| rgb-zh-46 | rgb | capability | rag_rgb | 2022年苹果春季发布会的新手机 | mixed |
| rgb-zh-132 | rgb | capability | rag_rgb | 2022年6月我国网民规模有多少人？ | mixed |
| rgb-zh-88 | rgb | capability | rag_rgb | 澳大利亚第31任总理是谁 | mixed |
| rgb-zh-229 | rgb | capability | rag_rgb | 果果合唱团是谁创办的？ | mixed |
| rgb-zh-94 | rgb | capability | rag_rgb | 2022年芦山地震是的震级 | mixed |
| rgb-zh-166 | rgb | capability | rag_rgb | 波兰要求德国赔偿二战损失多少钱 | mixed |
| rgb-zh-250 | rgb | capability | rag_rgb | 网易2022年全年营收多少？ | mixed |
| rgb-zh-232 | rgb | capability | rag_rgb | 暴雪游戏中国大陆终止运营时间 | mixed |
| rgb-zh-267 | rgb | capability | rag_rgb | 马英九访问大陆去了哪些城市 | mixed |
| rgb-zh-248 | rgb | capability | rag_rgb | 百度推出的类ChatGPT是什么？ | mixed |
| rgb-zh-85 | rgb | capability | rag_rgb | 《好好说话》的主演有哪些？ | mixed |
| rgb-zh-135 | rgb | capability | rag_rgb | 欧元区2022年8月通胀率是多少？ | mixed |
| rgb-zh-117 | rgb | capability | rag_rgb | 2022年下半年征兵报名截止时间是什么时候 | mixed |
| rgb-zh-198 | rgb | capability | rag_rgb | 首架C919的交付日时间？ | mixed |
| rgb-zh-144 | rgb | capability | rag_rgb | 《海的尽头是草原》改编自什么真实事件？ | mixed |
| rgb-zh-231 | rgb | capability | rag_rgb | 2022年中国研发经费总投入量是多少 | mixed |
| rgb-zh-263 | rgb | capability | rag_rgb | 马克龙访华时间？ | mixed |
| rgb-zh-170 | rgb | capability | rag_rgb | 第28届白玉兰颁奖时间 | mixed |
| rgb-zh-208 | rgb | capability | rag_rgb | 2023年北京新能源小客车指标有多少个？ | mixed |
| rgb-zh-256 | rgb | capability | rag_rgb | 2023年女足世界杯总奖金 | mixed |
| rgb-zh-247 | rgb | capability | rag_rgb | 2025年世界游泳锦标赛在哪里举办？ | mixed |
| rgb-zh-17 | rgb | capability | rag_rgb | 《李茂扮太子》是什么类型的电影 | mixed |
| rgb-zh-57 | rgb | capability | rag_rgb | 海底捞的新任首席执行官是谁？ | mixed |
| rgb-zh-159 | rgb | capability | rag_rgb | 阮富仲访华时间 | mixed |
| rgb-zh-184 | rgb | capability | rag_rgb | 台积电美国新厂计划投资多少 | mixed |
| rgb-zh-134 | rgb | capability | rag_rgb | 戈尔巴乔夫的葬礼将在哪里举行？ | mixed |
| rgb-zh-163 | rgb | capability | rag_rgb | 《三悦有了新工作》是哪个平台的 | mixed |
| rgb-zh-36 | rgb | capability | rag_rgb | 北京2022冬奥会高校志愿者有多少人 | mixed |
| rgb-zh-13 | rgb | capability | rag_rgb | 美国2021年GDP增长多少 | mixed |
| rgb-zh-156 | rgb | capability | rag_rgb | 特拉斯当了多久首相 | mixed |
| rgb-zh-167 | rgb | capability | rag_rgb | 2022年金鹰奖最佳电视剧 | mixed |
| rgb-zh-52 | rgb | capability | rag_rgb | 北京冬奥会男子500米速度滑冰金牌 | mixed |
| rgb-zh-145 | rgb | capability | rag_rgb | 伊丽莎白二世的国葬将在哪里举行？ | mixed |
| rgb-zh-168 | rgb | capability | rag_rgb | 2022美国中期选举改选的参议院席位 | mixed |
| rgb-zh-196 | rgb | capability | rag_rgb | 2023年春晚吉祥物是什么 | mixed |
| rgb-zh-6 | rgb | capability | rag_rgb | 2021年北京大兴机场年旅客吞吐量 | mixed |
| rgb-zh-25 | rgb | capability | rag_rgb | 苹果M1芯片首席设计师去了哪家公司 | mixed |
| rgb-zh-155 | rgb | capability | rag_rgb | 2023年亚洲杯举办国？  | mixed |
| rgb-zh-65 | rgb | capability | rag_rgb | 邓伦逃税了多少钱 | mixed |
| rgb-zh-129 | rgb | capability | rag_rgb | 2022年克利夫兰站女单冠军是谁 | mixed |
| swebench-django__django-14011 | swe-bench | capability | coding | LiveServerTestCase's ThreadedWSGIServer doesn't close databa | code |
| swebench-sphinx-doc__sphinx-9698 | swe-bench | capability | coding | An index entry with parens was registered for `py:method` di | code |
| swebench-pallets__flask-5014 | swe-bench | capability | coding | Require a non-empty name for Blueprints Things do not work c | code |
| swebench-django__django-11820 | swe-bench | capability | coding | models.E015 is raised when Meta.ordering contains "pk" of a  | code |
| swebench-scikit-learn__scikit-learn-26194 | swe-bench | capability | coding | Thresholds can exceed 1 in `roc_curve` while providing proba | code |
| swebench-sympy__sympy-23824 | swe-bench | capability | coding | physics.hep.kahane_simplify() incorrectly reverses order of  | code |
| swebench-sympy__sympy-19040 | swe-bench | capability | coding | Factor with extension=True drops a factor of y-1 I guess thi | code |
| swebench-django__django-15278 | swe-bench | capability | coding | Adding nullable OneToOneField crashes on SQLite. Description | code |
| swebench-django__django-12039 | swe-bench | capability | coding | Use proper whitespace in CREATE INDEX statements Description | code |
| swebench-pydata__xarray-6461 | swe-bench | capability | coding | xr.where with scalar as second argument fails with keep_attr | code |
| swebench-django__django-11149 | swe-bench | capability | coding | Admin inlines for auto-created ManyToManyFields are editable | code |
| swebench-sphinx-doc__sphinx-9591 | swe-bench | capability | coding | Cross-references don't work in property's type annotations # | code |
| swebench-sympy__sympy-18189 | swe-bench | capability | coding | diophantine: incomplete results depending on syms order with | code |
| swebench-sphinx-doc__sphinx-9320 | swe-bench | capability | coding | `sphinx-quickstart` with existing conf.py doesn't exit easil | code |
| swebench-sympy__sympy-13878 | swe-bench | capability | coding | Precompute the CDF of several distributions where integratio | code |
| swebench-matplotlib__matplotlib-25122 | swe-bench | capability | coding | [Bug]: Windows correction is not correct in `mlab._spectral_ | code |
| swebench-django__django-16116 | swe-bench | capability | coding | makemigrations --check generating migrations is inconsistent | code |
| swebench-sympy__sympy-18763 | swe-bench | capability | coding | Incorrect parenthesizing of Subs Here is an example. ```pyt | code |
| swebench-django__django-13964 | swe-bench | capability | coding | Saving parent object after setting on child leads to data lo | code |
| swebench-django__django-11885 | swe-bench | capability | coding | Combine fast delete queries Description 	 When emulating ON  | code |
| swebench-django__django-14238 | swe-bench | capability | coding | DEFAULT_AUTO_FIELD subclass check fails for subclasses of Bi | code |
| swebench-astropy__astropy-8707 | swe-bench | capability | coding | Header.fromstring does not accept Python 3 bytes According t | code |
| swebench-django__django-15368 | swe-bench | capability | coding | bulk_update() does not work with plain F('...') expressions. | code |
| swebench-sphinx-doc__sphinx-9367 | swe-bench | capability | coding | 1-element tuple rendered incorrectly **Describe the bug** T | code |
| swebench-django__django-15252 | swe-bench | capability | coding | MigrationRecorder does not obey db_router allow_migrate rule | code |
| swebench-django__django-15268 | swe-bench | capability | coding | Optimize multiple AlterFooTogether operations into one Descr | code |
| swebench-django__django-14534 | swe-bench | capability | coding | BoundWidget.id_for_label ignores id set by ChoiceWidget.opti | code |
| swebench-django__django-16560 | swe-bench | capability | coding | Allow to customize the code attribute of ValidationError rai | code |
| swebench-django__django-14539 | swe-bench | capability | coding | urlize() does not handle html escaped string and trailing pu | code |
| swebench-pydata__xarray-7393 | swe-bench | capability | coding | stack casts int32 dtype coordinate to int64 ### What happene | code |
| swebench-scikit-learn__scikit-learn-13439 | swe-bench | capability | coding | Pipeline should implement __len__ #### Description  With t | code |
| swebench-django__django-14089 | swe-bench | capability | coding | Allow calling reversed() on an OrderedSet Description 	 Curr | code |
| swebench-sphinx-doc__sphinx-8721 | swe-bench | capability | coding | viewcode creates pages for epub even if `viewcode_enable_epu | code |
| swebench-django__django-12858 | swe-bench | capability | coding | models.E015 is raised when ordering uses lookups that are no | code |
| swebench-psf__requests-1142 | swe-bench | capability | coding | requests.get is ALWAYS sending content length Hi,  It seems  | code |
| swebench-django__django-15572 | swe-bench | capability | coding | Django 3.2.4+ autoreload breaks on empty string in TEMPLATES | code |
| swebench-astropy__astropy-14309 | swe-bench | capability | coding | IndexError: tuple index out of range in identify_format (io. | code |
| swebench-django__django-13023 | swe-bench | capability | coding | DecimalField.to_python() raises TypeError on dict values. De | code |
| swebench-matplotlib__matplotlib-21568 | swe-bench | capability | coding | [Bug]: Datetime axis with usetex is unclear ### Bug summary  | code |
| swebench-pytest-dev__pytest-7571 | swe-bench | capability | coding | caplog fixture doesn't restore log level after test From the | code |
| tau2-retail-59 | tau2-bench | multi_turn | customer_service | You recently placed two orders, and now you would like to ma | mixed |
| tau2-retail-82 | tau2-bench | multi_turn | customer_service | You received two tablets and you only need one. You want to  | mixed |
| tau2-retail-19 | tau2-bench | multi_turn | customer_service | You want to return the water bottle, and exchange the pet be | mixed |
| tau2-retail-77 | tau2-bench | multi_turn | customer_service | You ordered a perfume and you just tried a little bit and yo | mixed |
| tau2-retail-11 | tau2-bench | multi_turn | customer_service | For some reason, you want to return all things ordered. You  | mixed |
| tau2-retail-57 | tau2-bench | multi_turn | customer_service | You wonder when is your order W4284542 is arriving. If it ha | mixed |
| tau2-retail-79 | tau2-bench | multi_turn | customer_service | You just bought a water bottle with 500ml but you regret it, | mixed |
| tau2-retail-14 | tau2-bench | multi_turn | customer_service | You just quit gaming and want to cancel or return everything | mixed |
| tau2-retail-108 | tau2-bench | multi_turn | customer_service | You want to return everything but a tablet in a recently del | mixed |
| tau2-retail-15 | tau2-bench | multi_turn | customer_service | You want to modify the pending boots to a size 8, and want t | mixed |
| tau2-retail-106 | tau2-bench | multi_turn | customer_service | You want to exchange your T-Shirt because it is too big, one | mixed |
| tau2-retail-73 | tau2-bench | multi_turn | customer_service | You want to return everything you just bought except the cof | mixed |
| tau2-retail-12 | tau2-bench | multi_turn | customer_service | You just got into gaming and want to cancel or return everyt | mixed |
| tau2-retail-103 | tau2-bench | multi_turn | customer_service | You want to return the bookshelf and jigsaw you received in  | mixed |
| tau2-retail-18 | tau2-bench | multi_turn | customer_service | You want to return the office chair because it came with som | mixed |
| tau2-retail-27 | tau2-bench | multi_turn | customer_service | From a recent order, you want to return the hose, backpack,  | mixed |
| tau2-retail-65 | tau2-bench | multi_turn | customer_service | You want to exchange the bookshelf from your most recent ord | mixed |
| tau2-retail-35 | tau2-bench | multi_turn | customer_service | You want to return the speaker that is more expensive yet no | mixed |
| tau2-retail-110 | tau2-bench | multi_turn | customer_service | You live on Elm Avenue in Houston, and recently you moved to | mixed |
| tau2-retail-83 | tau2-bench | multi_turn | customer_service | You received two tablets and you only need one. You want to  | mixed |
| tau2-retail-33 | tau2-bench | multi_turn | customer_service | You had a work-from-home situation and ordered three home of | mixed |
| tau2-retail-74 | tau2-bench | multi_turn | customer_service | You recently bought a laptop, but you want to exchange it to | mixed |
| tau2-retail-113 | tau2-bench | multi_turn | customer_service | You want to cancel all pending orders. | mixed |
| tau2-retail-36 | tau2-bench | multi_turn | customer_service | You just placed an order but you realize that your card has  | mixed |
| tau2-retail-71 | tau2-bench | multi_turn | customer_service | You made some mistake and ordered an order sent to your son' | mixed |
| tau2-retail-95 | tau2-bench | multi_turn | customer_service | You received a laptop and you want to exchange it to i7 proc | mixed |
| tau2-retail-98 | tau2-bench | multi_turn | customer_service | You want to exchange your Bicycle for one with a larger fram | mixed |
| tau2-retail-20 | tau2-bench | multi_turn | customer_service | You just won a lottery, and you want to upgrade all your ite | mixed |
| tau2-retail-109 | tau2-bench | multi_turn | customer_service | You live on Elm Avenue in Houston, and recently you moved to | mixed |
| tau2-retail-22 | tau2-bench | multi_turn | customer_service | You want to change your user address and all possible order  | mixed |
| tau2-retail-53 | tau2-bench | multi_turn | customer_service | The bicycle you received was damaged during delivery, and yo | mixed |
| tau2-retail-9 | tau2-bench | multi_turn | customer_service | You want to exchange the water bottle and the desk lamp. You | mixed |
| tau2-retail-30 | tau2-bench | multi_turn | customer_service | You just received your tablet and it was damaged when you op | mixed |
| tau2-retail-48 | tau2-bench | multi_turn | customer_service | You want to return an air purifier that you received since i | mixed |
| tau2-retail-92 | tau2-bench | multi_turn | customer_service | You are angry about the quality of the two skateboards you j | mixed |
| tau2-retail-52 | tau2-bench | multi_turn | customer_service | The digital camera you received doesn't zoom as far as you e | mixed |
| tau2-retail-87 | tau2-bench | multi_turn | customer_service | You want to modify all your pending order address to the Was | mixed |
| tau2-retail-26 | tau2-bench | multi_turn | customer_service | You have an order sent to Texas by accident, and you want to | mixed |
| tau2-retail-56 | tau2-bench | multi_turn | customer_service | You wonder when is your air purifier is arriving. If it has  | mixed |
| tau2-retail-72 | tau2-bench | multi_turn | customer_service | You made some mistake and sent an order your son's address i | mixed |
| webarena-360 | webarena | capability | web | Show me the product names for order number 148. | code |
| webarena-625 | webarena | capability | web | Create a discussion post about "the effectiveness of online  | code |
| webarena-709 | webarena | capability | web | Create an orders report from beginning of May 2021 to end of | code |
| webarena-306 | webarena | capability | web | How many commits did Anthony make between 08/2022-09/2022? | code |
| webarena-173 | webarena | capability | web | Open my latest updated issue that has keyword "better" in it | code |
| webarena-472 | webarena | capability | web | Cancel order 299 | code |
| webarena-352 | webarena | capability | web | List products from nutrition bars and drinks category by asc | code |
| webarena-125 | webarena | capability | web | What is the price range of teeth grinding mouth guard in the | code |
| webarena-212 | webarena | capability | web | Find the customer name and email with phone number 555-229-3 | code |
| webarena-783 | webarena | capability | web | Add the following users to repo kkroening/ffmpeg-python as m | code |
| webarena-380 | webarena | capability | web | Find the bar around Carnegie Music Hall | code |
| webarena-599 | webarena | capability | web | Open the thread of a trending post on the forum "machine lea | code |
| webarena-568 | webarena | capability | web | Invite Abishek and Vinta as collaborator to a11yproject.com  | code |
| webarena-495 | webarena | capability | web | Notify Lily Potter in their most recent pending order with m | code |
| webarena-766 | webarena | capability | web | Find the walkway to the closest grocessory owned by Amazon f | code |
| webarena-26 | webarena | capability | web | List out reviewers, if exist, who mention about complain of  | code |
| webarena-224 | webarena | capability | web | I am at CMU Pittsburgh, how long it takes to drive to the ne | code |
| webarena-735 | webarena | capability | web | Edit my post on Lord of the Rings by adding a line to the bo | code |
| webarena-65 | webarena | capability | web | Which customer has completed the fifth most number of orders | code |
| webarena-531 | webarena | capability | web | Draft a refund message via their "contact us" form for the p | code |
| webarena-323 | webarena | capability | web | How much refund I should expect from my order canlled in 202 | code |
| webarena-649 | webarena | capability | web | Post in history subreddit about what could diffusion model h | code |
| webarena-252 | webarena | capability | web | Tell me the coordinates of Tokyo Japanese Food Store in Pitt | code |
| webarena-793 | webarena | capability | web | Buy the highest rated product from the Men clothing category | code |
| webarena-123 | webarena | capability | web | Tell me the reasons why customers like Circe's products | code |
| webarena-430 | webarena | capability | web | Find the page of the college(s) where The Chair was filmed i | code |
| webarena-520 | webarena | capability | web | Add this product to my wishlist | code |
| webarena-784 | webarena | capability | web | Tell me the email address of the contributor who has the mos | code |
| webarena-677 | webarena | capability | web | Lookup orders that are processing | code |
| webarena-135 | webarena | capability | web | How many commits did Eric and Kilian make to a11yproject on  | code |
| webarena-287 | webarena | capability | web | How much time does it take from Pittsburgh to Philadelphia b | code |
| webarena-496 | webarena | capability | web | Update order #299 with the Federal Express tracking number 8 | code |
| webarena-358 | webarena | capability | web | Show me the shipping method for order number 187. | code |
| webarena-83 | webarena | capability | web | What is the duration required to first walk from Carnegie Me | code |
| webarena-423 | webarena | capability | web | Mark all Hollister shirts on sale | code |
| webarena-326 | webarena | capability | web | Show me the "Canon photo printer" listings by search relevan | code |
| webarena-103 | webarena | capability | web | Display the list of issues in the kkroening/ffmpeg-python re | code |
| webarena-404 | webarena | capability | web | Upvote the newest post in books subreddit | code |
| webarena-77 | webarena | capability | web | What is the total count of Pending reviews amongst all the r | code |
| webarena-12 | webarena | capability | web | Tell me the the number of reviews that our store received by | code |
