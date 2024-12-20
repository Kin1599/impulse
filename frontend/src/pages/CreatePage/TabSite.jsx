import React, {useState} from "react";
import styles from "./CreatePage.module.scss";
import {Button, ColorPicker, Input, Select, Upload} from "antd";
import TextArea from "antd/es/input/TextArea";
import classNames from "classnames";
import {useDispatch, useSelector} from "react-redux";
import {addElement, fetchData} from "../../slices/botSlice";
import {useNavigate} from "react-router-dom";
import {UploadOutlined} from "@ant-design/icons";

const TabSite = () => {
	const [title, setTitle] = useState("");
	const [desc, setDesc] = useState("");
	const [logo, setLogo] = useState(null);
	const [font, setFont] = useState("");
	const [color, setColor] = useState("#00aae6");
	const navigate = useNavigate();

	const {data, services, settings, activeRetriver, activeLlm, prompt} = useSelector(s => s.createBot);
	const items = useSelector(s => s.bot.items);

	const dispatch = useDispatch();

	const handleUpload = file => {
		const reader = new FileReader();
		reader.onload = () => {
			setLogo(reader.result); // Записываем изображение в виде base64
		};
		reader.readAsDataURL(file);
		return false; // Возвращаем false, чтобы предотвратить автоматическую загрузку файла
	};

	const handleSubmitClick = () => {
		const req = {
			services,
			settings: {
				temp: 0,
			},
			activeRetriver,
			activeLlm,
			prompt,
		};
		const res = {
			title,
			desc,
			logo,
			font,
			color,
		};
		console.log(logo);
		dispatch(fetchData(req));
		dispatch(addElement({...res, ...req, id: items?.length + 1, popup: false}));
		navigate(`/${items?.length + 1}`);
	};

	const generateFontStyle = () => {
		if (!font) return null;
		return <style>{`@import url('https://fonts.googleapis.com/css2?family=${font.replace(/\s/g, "+")}:wght@400;700&display=swap');`}</style>;
	};

	const options = [
		{
			value: "roboto",
			label: "Roboto",
		},
		{
			value: "inter",
			label: "Inter",
		},
		{
			value: "Montserrat",
			label: "Montserrat",
		},
	];

	return (
		<div className={styles.tab}>
			{generateFontStyle()}
			<div className={styles.topTab}>
				<div className={styles.rigt}>
					<div className={styles.elem}>
						<div className={styles.subsubTitle}>Название</div>
						<Input value={title} onChange={e => setTitle(e.target.value)} />
					</div>
					<div className={classNames(styles.elem, styles.lElem)}>
						<div className={styles.subsubTitle}>Описание</div>
						<TextArea className={styles.textArea} value={desc} onChange={e => setDesc(e.target.value)} />
					</div>
				</div>
				<div className={styles.rigt}>
					<div className={styles.elem}>
						<div className={styles.subsubTitle}>Логотип</div>
						<Upload beforeUpload={handleUpload} accept='image/*'>
							<Button icon={<UploadOutlined />}>Загрузить логотип</Button>
						</Upload>
					</div>
					<div className={styles.elem}>
						<div className={styles.subsubTitle}>Шрифт</div>
						<Select options={options} value={font} onChange={e => setFont(e)} placeholder='Введите название шрифта, напр. Roboto' />
					</div>
					<div className={styles.elem}>
						<div className={styles.subsubTitle}>Основной цвет</div>
						<div className={styles.divdiv}>
							<ColorPicker defaultValue={"#00aae6"} value={color} onChange={(v, css) => setColor(css)} />
							<Input value={color} onChange={e => setColor(e.target.value)} placeholder='Введите цвет, напр. #ff5733 или red' />
						</div>
					</div>
				</div>
			</div>
			<div className={styles.subTitle}>Предпросмотр</div>
			<div className={styles.preview}>
				<div className={styles.previewContainer}>
					<div
						className={styles.previewLogo}
						style={{
							backgroundImage: logo ? `url(${logo})` : undefined,
							backgroundSize: "contain",
							backgroundRepeat: "no-repeat",
							backgroundPosition: "center",
							backgroundColor: logo ? "inherit" : "gray",
						}}></div>
					<div
						className={styles.subTitle}
						style={{
							fontFamily: font || "inherit",
							color: color || "black",
						}}>
						{title || "Lorem Ipsum"}
					</div>
					<div
						style={{
							fontFamily: font || "inherit",
						}}>
						{desc || "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."}
					</div>
					<div className={styles.previewEl}>
						<div>Input</div>
						<TextArea disabled />
						<Button
							type='primary'
							className={styles.miniBtn}
							style={{
								backgroundColor: color || "#1890ff",
							}}>
							Отправить
						</Button>
					</div>
					<div className={styles.previewEl}>
						<div>Output</div>
						<TextArea disabled />
					</div>
				</div>
			</div>
			<Button style={{width: "20%", margin: "30px auto"}} type='primary' onClick={handleSubmitClick}>
				Сохранить
			</Button>
		</div>
	);
};

export default React.memo(TabSite);
